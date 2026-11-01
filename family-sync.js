/* Mon Panier : synchronisation volontaire des courses familiales.
   Le stockage local reste disponible sans compte. Aucun secret serveur ici. */
(() => {
  'use strict';
  const API = 'https://82.66.229.233';
  const AUTH_KEY = 'mon-panier-family-auth-v1';
  const LINK_KEY = 'mon-panier-family-linked-v1';
  const OUTBOX_KEY = 'mon-panier-family-outbox-v1';
  const STAR_OUTBOX_KEY = 'mon-panier-family-star-pending-v1';
  const STAR_IMPORTED_KEY = 'mon-panier-family-stars-imported-v1';
  const adapter = window.MonPanierFamilyAdapter;
  if (!adapter) return;

  const session = { token: localStorage.getItem(AUTH_KEY) || '', household: null,
    profile: null, mode: 'offline', message: '', invitation: '', lastEvent: 0,
    versions: {}, busy: false, pending: new Set(), queued: new Set(), generations: new Map(), favoritePending: {}, favoriteFlushing: false };

  function escapeHTML(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, ch =>
      ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  }
  function setMessage(value) { session.message = value; renderPanel(); }
  function week() { return adapter.week(); }
  function householdPath(path) {
    return '/api/households/' + encodeURIComponent(session.household.id) + path;
  }
  async function request(path, method, payload) {
    const headers = { 'Accept': 'application/json' };
    if (payload !== undefined) headers['Content-Type'] = 'application/json';
    if (session.token) headers['Authorization'] = 'Bearer ' + session.token;
    const options = { method: method || 'GET', headers, cache: 'no-store' };
    if (payload !== undefined) options.body = JSON.stringify(payload);
    let response;
    try { response = await fetch(API + path, options); }
    catch (_) { throw new Error('API indisponible : vérifiez Internet et le serveur familial.'); }
    let body = {};
    try { body = await response.json(); } catch (_) {}
    if (!response.ok) {
      if (response.status === 401 && !path.endsWith('/login') && !path.endsWith('/join')) {
        session.token = ''; localStorage.removeItem(AUTH_KEY); session.mode = 'offline';
      }
      throw new Error(typeof body.detail === 'string' ? body.detail : 'Erreur HTTP ' + response.status);
    }
    return body;
  }
  function localKey() {
    return session.household ? session.household.id + ':' + week() : '';
  }
  function persistOutbox() {
    localStorage.setItem(OUTBOX_KEY, JSON.stringify({ key: localKey(), commands: [...session.queued] }));
  }
  function isLinked() { return localStorage.getItem(LINK_KEY) === localKey(); }
  function backup() {
    const key = 'mon-panier-before-family-' + week();
    if (!localStorage.getItem(key)) localStorage.setItem(key, adapter.backup());
  }
  function setMode(mode, message) {
    session.mode = mode;
    session.message = message || '';
    renderPanel();
  }
  function snapshotVersions(rows) {
    session.versions = {};
    rows.forEach(r => { session.versions[r.ingredient_key] = Number(r.version) || 1; });
  }
  async function snapshotAndApply() {
    const data = await request(householdPath('/snapshot?week=' + week()));
    backup();
    snapshotVersions(data.shopping || []);
    session.lastEvent = data.last_event_id || 0;
    adapter.apply(data.shopping || []);
    const favorites=(data.favorites||[]).filter(row=>!(row.recipe_key in session.favoritePending));
    for(const [key,starred] of Object.entries(session.favoritePending))favorites.push({recipe_key:key,starred});
    adapter.applyFavorites(favorites);
    renderPanel();
  }
  function favoritePendingKey() {
    return session.household ? STAR_OUTBOX_KEY + ':' + session.household.id : '';
  }
  function loadFavoritePending() {
    try { const pending = JSON.parse(localStorage.getItem(favoritePendingKey()));
      session.favoritePending = pending && typeof pending === 'object' && !Array.isArray(pending) ? pending : {};
    } catch (_) { session.favoritePending = {}; }
  }
  function persistFavoritePending() {
    if (session.household) localStorage.setItem(favoritePendingKey(), JSON.stringify(session.favoritePending));
  }
  async function flushFavorites() {
    if (!session.household || !session.token || session.favoriteFlushing) return;
    session.favoriteFlushing = true;
    try {
      while (Object.keys(session.favoritePending).length) {
        const [key,starred] = Object.entries(session.favoritePending)[0];
        try {
          await request(householdPath('/favorites/' + encodeURIComponent(key)), 'PUT', {starred:Boolean(starred)});
          if (session.favoritePending[key] === starred) delete session.favoritePending[key];
          persistFavoritePending();
        } catch (error) {
          session.message = '⚠ Favoris en attente : ' + error.message;
          break;
        }
      }
    } finally { session.favoriteFlushing = false; }
  }
  function setFavorite(key,starred) {
    if (!session.household) return;
    session.favoritePending[key] = Boolean(starred);
    persistFavoritePending();
    if (session.mode === 'live') void flushFavorites();
  }
  async function seedLocalStars() {
    const marker = STAR_IMPORTED_KEY + ':' + session.household.id;
    if (localStorage.getItem(marker) === 'yes') return;
    for (const key of Object.keys(adapter.favorites())) {
      // Migration additive : on conserve les favoris présents sur ce téléphone.
      await request(householdPath('/favorites/' + encodeURIComponent(key)), 'PUT', {starred:true});
    }
    localStorage.setItem(marker, 'yes');
  }
  async function syncArchives() {
    const before = await request(householdPath('/archives'));
    const remoteWeeks = new Set((before.archives||[]).map(a=>a.week_key));
    let wrote = false;
    for (const archive of adapter.archives()) {
      if (!/^\d{4}-\d\d-\d\d$/.test(archive.key) || remoteWeeks.has(archive.key)) continue;
      const payload = adapter.archivePayload(archive);
      if (!payload.plan?.flat().every(key=>payload.recipes[key])) continue;
      await request(householdPath('/archives/' + archive.key), 'PUT', payload);
      wrote = true;
    }
    const data = wrote ? await request(householdPath('/archives')) : before;
    adapter.applyArchives(data.archives||[]);
  }
  function archiveWeek(archive) {
    // La sauvegarde locale existe déjà ; au prochain démarrage, syncArchives retentera l'envoi.
    if (!session.household || session.mode !== 'live') return;
    const payload = adapter.archivePayload(archive);
    if (!payload.plan?.flat().every(key=>payload.recipes[key])) return;
    void request(householdPath('/archives/' + archive.key),'PUT',payload)
      .then(()=>syncArchives())
      .catch(e=>setMessage('⚠ Archive locale conservée, envoi à reprendre : '+e.message));
  }
  async function syncExtras() {
    try {
      await seedLocalStars();
      await flushFavorites();
      await syncArchives();
    } catch (error) { session.message = '⚠ Archives ou favoris : '+error.message+' (les courses restent utilisables).'; }
  }
  async function start() {
    if (!session.token) { setMode('offline'); return; }
    setMode('connecting', 'Connexion à la famille…');
    try {
      const me = await request('/api/me');
      session.profile = me.profile;
      session.household = (me.households || [])[0] || null;
      if (!session.household) throw new Error('Ce compte ne fait partie d’aucune famille.');
      loadFavoritePending();
      if (isLinked()) {
        let oldOutbox = null;
        try { oldOutbox = JSON.parse(localStorage.getItem(OUTBOX_KEY)); } catch (_) {}
        if (oldOutbox?.key === localKey() && Array.isArray(oldOutbox.commands)) {
          session.queued = new Set(oldOutbox.commands.filter(c => /^(put|delete):[\w-]{1,100}$/.test(c)));
        }
        if (session.queued.size) {
          const previous = await request(householdPath('/snapshot?week=' + week()));
          snapshotVersions(previous.shopping || []);
          setMode('live', 'Envoi des changements conservés hors ligne…');
          await flush();
          if (session.queued.size) return;
        }
        await syncExtras();
        await snapshotAndApply();
        setMode('live', session.message.startsWith('⚠')?session.message:'Vos achats, favoris et archives sont partagés avec la famille.');
      } else {
        setMode('choose', 'Choisissez comment réunir les courses de ce téléphone avec la famille.');
      }
    } catch (error) { setMode(session.token ? 'error' : 'offline', error.message); }
  }
  async function link(action) {
    if (!session.household || session.busy) return;
    session.busy = true;
    setMode('connecting', 'Préparation de la liste familiale…');
    try {
      const localRows = adapter.rows().filter(r => r.is_bought || r.is_manual || r.unavailable_stores?.length);
      backup();
      if (action === 'import') {
        // Import ADDITIF : ne pas décocher un achat partagé lorsqu'on importe un signalement magasin.
        const current = await request(householdPath('/snapshot?week=' + week()));
        const remote = new Map((current.shopping||[]).map(item=>[item.ingredient_key,item]));
        for (const row of localRows) {
          const existing = remote.get(row.key);
          const unavailable = [...new Set([...(existing?.unavailable_stores||[]),...(row.unavailable_stores||[])])];
          await request(householdPath('/shopping/' + week() + '/' + encodeURIComponent(row.key)), 'PUT', {
            name: row.name, quantity_text: row.quantity_text,
            store_name: existing?.store_name||row.store_name,
            is_bought: Boolean(row.is_bought || existing?.is_bought), unavailable_stores: unavailable
          });
        }
      }
      localStorage.setItem(LINK_KEY, localKey());
      await syncExtras();
      await snapshotAndApply();
      setMode('live', 'Synchronisation familiale activée.');
    } catch (error) {
      setMode('choose', error.message + ' Réessayez. Aucune donnée locale n’a été supprimée.');
    } finally { session.busy = false; }
  }
  function recordChange(key, removed) {
    if (session.mode !== 'live') return;
    const command = (removed ? 'delete:' : 'put:') + key;
    session.generations.set(command, (session.generations.get(command) || 0) + 1);
    session.queued.add(command);
    persistOutbox();
    void flush();
  }
  async function flush() {
    if (session.busy || session.mode !== 'live' || !session.queued.size) return;
    session.busy = true;
    try {
      while (session.queued.size) {
        const command = session.queued.values().next().value;
        const removed = command.startsWith('delete:');
        const generation = session.generations.get(command) || 0;
        const key = command.slice(removed ? 7 : 4);
        const path = householdPath('/shopping/' + week() + '/' + encodeURIComponent(key));
        if (removed) {
          await request(path, 'DELETE');
          delete session.versions[key];
        } else {
          const row = adapter.rows().find(r => r.key === key);
          if (!row) { session.queued.delete(command); persistOutbox(); continue; }
          const saved = await request(path, 'PUT', {
            name: row.name, quantity_text: row.quantity_text, store_name: row.store_name,
            is_bought: Boolean(row.is_bought), unavailable_stores: row.unavailable_stores,
            expected_version: session.versions[key] || 0
          });
          session.versions[key] = Number(saved.version) || 1;
        }
        if ((session.generations.get(command) || 0) === generation) session.queued.delete(command);
        persistOutbox();
      }
      session.message = 'Achats enregistrés pour toute la famille.';
    } catch (error) {
      session.message = '⚠ ' + error.message + ' Les changements restent visibles sur cet appareil. Appuyez sur Réessayer.';
    } finally {
      session.busy = false; renderPanel();
    }
  }
  async function poll() {
    if (session.busy || session.mode !== 'live' || document.visibilityState !== 'visible') return;
    if (!isLinked()) { setMode('choose', 'Nouvelle semaine : choisissez la liste familiale.'); return; }
    if (session.queued.size) { await flush(); return; }
    if (Object.keys(session.favoritePending).length) await flushFavorites();
    session.busy = true;
    try {
      const data = await request(householdPath('/events?after=' + session.lastEvent));
      if ((data.events || []).length) {
        if (data.events.some(e=>e.kind==='archive.saved')) await syncArchives();
        await snapshotAndApply();
        session.message = 'Achats et favoris actualisés depuis les autres téléphones.';
      }
    } catch (error) { session.message = '⚠ Synchronisation en attente : ' + error.message; }
    finally { session.busy = false; renderPanel(); }
  }
  async function login(form) {
    const input = new FormData(form);
    setMode('connecting', 'Connexion…');
    try {
      const data = await request('/api/login', 'POST', {
        email: String(input.get('email') || ''), password: String(input.get('password') || '')
      });
      session.token = data.access_token;
      localStorage.setItem(AUTH_KEY, session.token);
      await start();
    } catch (error) { setMode('offline', error.message); }
  }
  async function join(form) {
    const input = new FormData(form);
    setMode('connecting', 'Création du compte…');
    try {
      const data = await request('/api/join', 'POST', {
        email: String(input.get('email') || ''),
        display_name: String(input.get('display_name') || ''),
        password: String(input.get('password') || ''),
        invitation: String(input.get('invitation') || '').trim()
      });
      session.token = data.access_token;
      localStorage.setItem(AUTH_KEY, session.token);
      await start();
    } catch (error) { setMode('offline', error.message); }
  }
  async function invitation() {
    try {
      const data = await request(householdPath('/invitations'), 'POST');
      session.invitation = data.invitation;
      session.message = 'Invitation valable 48 heures. Transmettez ce code uniquement à votre famille.';
      renderPanel();
    } catch (error) { setMessage(error.message); }
  }
  function logout() {
    session.token = ''; session.household = null; session.profile = null;
    session.queued.clear(); session.generations.clear(); session.favoritePending={}; session.invitation = ''; session.lastEvent = 0;
    localStorage.removeItem(AUTH_KEY);
    setMode('offline', 'Déconnecté. Les données déjà présentes sur cet appareil sont conservées.');
  }
  function renderPanel() {
    const target = document.getElementById('family-sync-panel');
    if (!target) return;
    let content = '<div class="card sheet" style="margin-bottom:16px"><h2 style="margin:0 0 8px">👨‍👩‍👧‍👦 Courses en famille</h2>';
    if (session.mode === 'offline' || session.mode === 'error') {
      content += '<p class="small">Connectez chaque téléphone à votre famille pour retrouver les coches en direct. Sans connexion, votre liste locale reste utilisable.</p>'
       + '<form id="family-login" class="manual-add" autocomplete="on"><input class="field" type="email" name="email" autocomplete="username" placeholder="Adresse e-mail" required>'
       + '<input class="field" type="password" name="password" autocomplete="current-password" placeholder="Mot de passe" required>'
       + '<button class="btn" type="submit">Se connecter</button></form>'
       + '<details style="margin-top:10px"><summary>Je rejoins la famille avec un code</summary>'
       + '<form id="family-join" class="manual-add" style="margin-top:10px"><input class="field" name="invitation" placeholder="Code d’invitation" required>'
       + '<input class="field" type="email" name="email" autocomplete="email" placeholder="Mon e-mail" required>'
       + '<input class="field" name="display_name" placeholder="Prénom" required>'
       + '<input class="field" type="password" name="password" autocomplete="new-password" minlength="12" placeholder="Mot de passe (12 caractères minimum)" required>'
       + '<button class="btn" type="submit">Rejoindre</button></form></details>';
    } else if (session.mode === 'connecting') {
      content += '<p>⏳ Connexion à la base familiale…</p>';
    } else {
      content += '<p class="small"><b>' + escapeHTML(session.profile?.display_name || '') + '</b> · ' +
        escapeHTML(session.household?.name || '') + '</p>';
      if (session.mode === 'choose') {
        content += '<p>Vos coches enregistrées sur ce téléphone ne seront pas supprimées sans sauvegarde.</p>'
          + '<div class="mini-links"><button class="btn" data-family="receive">📥 Voir la liste familiale</button>'
          + '<button class="btn btn-outline" data-family="import">➕ Ajouter mes achats cochés</button></div>'
          + '<p class="small muted">« Ajouter » fusionne les achats cochés avec ceux déjà partagés ; cela ne décoche pas ceux des autres.</p>';
      } else if (session.mode === 'live') {
        content += '<p>✅ <b>Synchronisation active</b> · vérification automatique toutes les 8 secondes.</p>'
          + '<div class="mini-links"><button class="btn btn-outline btn-small" data-family="refresh">🔄 Actualiser</button>'
          + '<button class="btn btn-outline btn-small" data-family="retry">Réessayer un envoi</button></div>';
      }
      if (session.household?.role === 'owner') {
        content += '<details style="margin-top:8px"><summary>Inviter un membre de la famille</summary>'
          + '<button class="btn btn-outline btn-small" data-family="invite" style="margin-top:8px">Créer un code (48 h)</button>';
        if (session.invitation) {
          content += '<input class="field" style="margin-top:8px;width:100%" readonly value="' + escapeHTML(session.invitation) + '" aria-label="Code d’invitation">'
            + '<button class="btn btn-outline btn-small" data-family="copy-invite">📋 Copier le code</button>';
        }
        content += '</details>';
      }
      content += '<div style="margin-top:12px"><button class="btn btn-outline btn-small" data-family="logout">Se déconnecter</button></div>';
    }
    if (session.message) content += '<p class="small" role="status">' + escapeHTML(session.message) + '</p>';
    content += '</div>';
    target.innerHTML = content;
  }
  document.addEventListener('submit', event => {
    if (event.target.id === 'family-login') { event.preventDefault(); void login(event.target); }
    if (event.target.id === 'family-join') { event.preventDefault(); void join(event.target); }
  });
  document.addEventListener('click', event => {
    const button = event.target.closest('[data-family]');
    if (!button) return;
    const action = button.dataset.family;
    if (action === 'receive') void link('receive');
    if (action === 'import') void link('import');
    if (action === 'refresh') void snapshotAndApply().catch(e => setMessage(e.message));
    if (action === 'retry') { void flush(); void flushFavorites(); void syncArchives().catch(e=>setMessage(e.message)); }
    if (action === 'invite') void invitation();
    if (action === 'logout') logout();
    if (action === 'copy-invite' && session.invitation) {
      if (navigator.clipboard?.writeText) void navigator.clipboard.writeText(session.invitation);
      else window.prompt('Copiez le code :', session.invitation);
    }
  });

  window.MonPanierFamily = { renderPanel, recordChange, setFavorite, archiveWeek };
  window.addEventListener('mon-panier:render', renderPanel);
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') void poll(); });
  setInterval(() => { void poll(); }, 8000);
  renderPanel();
  if (session.token) void start();
})();