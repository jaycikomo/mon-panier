/* Mon Panier : synchronisation volontaire des courses familiales.
   Le stockage local reste disponible sans compte. Aucun secret serveur ici. */
(() => {
  'use strict';
  const API = 'https://82.66.229.233';
  const AUTH_KEY = 'mon-panier-family-auth-v1';
  const REFRESH_KEY = 'mon-panier-family-refresh-v1';
  const LINK_KEY = 'mon-panier-family-linked-v1';
  const OUTBOX_KEY = 'mon-panier-family-outbox-v1';
  const STAR_OUTBOX_KEY = 'mon-panier-family-star-pending-v1';
  const STAR_IMPORTED_KEY = 'mon-panier-family-stars-imported-v1';
  const PROGRESS_OUTBOX_KEY = 'mon-panier-recipe-progress-outbox-v1';
  const PROGRESS_IMPORTED_KEY = 'mon-panier-recipe-progress-imported-v1';
  const adapter = window.MonPanierFamilyAdapter;
  let resetCode = new URLSearchParams(window.location.hash.slice(1)).get('reset');
  if (!adapter) return;
  if (resetCode) adapter.openAccount();

  const session = { token: localStorage.getItem(AUTH_KEY) || '',
    refreshToken: localStorage.getItem(REFRESH_KEY) || '', household: null,
    profile: null, mode: 'offline', message: '', invitation: '', lastEvent: 0,
    versions: {}, busy: false, pending: new Set(), queued: new Set(), generations: new Map(), favoritePending: {}, favoriteFlushing: false, menuVersion: null, menuSaving: false,
    progressPending: {}, progressFlushing: false, syncedWeek: null };

  function escapeHTML(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, ch =>
      ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  }
  function setMessage(value) { session.message = value; renderPanel(); }
  function week() { return adapter.week(); }
  function householdPath(path) {
    return '/api/households/' + encodeURIComponent(session.household.id) + path;
  }
  function keepSession(data) {
    session.token = data.access_token || '';
    session.refreshToken = data.refresh_token || '';
    if (session.token) localStorage.setItem(AUTH_KEY,session.token);
    else localStorage.removeItem(AUTH_KEY);
    if (session.refreshToken) localStorage.setItem(REFRESH_KEY,session.refreshToken);
    else localStorage.removeItem(REFRESH_KEY);
  }
  function clearCredentials() {
    session.token='';session.refreshToken='';
    localStorage.removeItem(AUTH_KEY);localStorage.removeItem(REFRESH_KEY);
  }
  let refreshing = null;
  async function refreshAccess() {
    if (!session.refreshToken) throw new Error('Reconnectez-vous pour activer la connexion durable.');
    if (refreshing) return refreshing;
    refreshing = (async () => {
      let response;
      try {
        response = await fetch(API + '/api/session/refresh', {
          method:'POST',headers:{'Content-Type':'application/json','Accept':'application/json'},
          body:JSON.stringify({refresh_token:session.refreshToken}),cache:'no-store'
        });
      } catch (_) { throw new Error('Serveur familial injoignable : session conservée pour réessayer.'); }
      if (!response.ok) {
        if (response.status === 401) clearCredentials();
        throw new Error('Renouvellement impossible : reconnectez-vous.');
      }
      keepSession(await response.json());
    })();
    try { await refreshing; } finally { refreshing=null; }
  }
  async function request(path, method, payload, retry=false) {
    const headers = { 'Accept': 'application/json' };
    if (payload !== undefined) headers['Content-Type'] = 'application/json';
    if (session.token) headers['Authorization'] = 'Bearer ' + session.token;
    const options = { method: method || 'GET', headers, cache: 'no-store' };
    if (payload !== undefined) options.body = JSON.stringify(payload);
    let response;
    try { response = await fetch(API + path, options); }
    catch (_) { throw new Error('API indisponible : vérifiez Internet et le serveur familial.'); }
    if (response.status === 401 && !retry && session.refreshToken &&
        !['/api/login','/api/join','/api/session/refresh'].includes(path)) {
      await refreshAccess();
      return request(path,method,payload,true);
    }
    let body = {};
    try { body = await response.json(); } catch (_) {}
    if (!response.ok) {
      if (response.status === 401 && !path.endsWith('/login') && !path.endsWith('/join')) {
        clearCredentials();session.mode = 'offline';
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
  function isLinked() {
    if (!session.household) return false;
    const marker=localStorage.getItem(LINK_KEY)||'';
    // Compatibilite avec les anciennes associations limitees a une semaine.
    return marker===session.household.id || marker.startsWith(session.household.id+':');
  }
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
    const progress=(data.progress||[]).filter(r=>!(r.recipe_key in session.progressPending));
    for(const [key,done] of Object.entries(session.progressPending))progress.push({recipe_key:key,is_done:done});
    adapter.applyProgress(progress);
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
  async function syncExtras(importLocal=true) {
    try {
      if(importLocal)await seedLocalStars();
      await flushFavorites();
      if(importLocal)await seedLocalProgress();
      await flushProgress();
      await syncArchives();
    } catch (error) { session.message = '⚠ Archives ou favoris : '+error.message+' (les courses restent utilisables).'; }
  }
  function progressKey() {
    return PROGRESS_OUTBOX_KEY+':'+session.household.id+':'+week();
  }
  function loadProgressPending() {
    try{
      const value=JSON.parse(localStorage.getItem(progressKey()));
      session.progressPending=value&&typeof value==='object'&&!Array.isArray(value)?value:{};
    }catch(_){session.progressPending={};}
  }
  function persistProgress() {
    if(session.household)localStorage.setItem(progressKey(),JSON.stringify(session.progressPending));
  }
  async function flushProgress() {
    if(!session.household||!session.token||session.progressFlushing)return;
    session.progressFlushing=true;
    try{
      while(Object.keys(session.progressPending).length){
        const [key,done]=Object.entries(session.progressPending)[0];
        try{
          await request(householdPath('/recipe-progress/'+week()+'/'+encodeURIComponent(key)),
            'PUT',{is_done:Boolean(done)});
          if(session.progressPending[key]===done)delete session.progressPending[key];
          persistProgress();
        }catch(e){session.message='⚠ Statut des recettes en attente : '+e.message;break;}
      }
    }finally{session.progressFlushing=false;}
  }
  function recordRecipeDone(key,done) {
    if(!session.household)return;
    session.progressPending[key]=Boolean(done);
    persistProgress();
    if(session.mode==='live')void flushProgress();
  }
  async function seedLocalProgress() {
    const marker=PROGRESS_IMPORTED_KEY+':'+session.household.id+':'+week();
    if(localStorage.getItem(marker)==='yes')return;
    for(const key of Object.keys(adapter.progress()))
      await request(householdPath('/recipe-progress/'+week()+'/'+encodeURIComponent(key)),'PUT',{is_done:true});
    localStorage.setItem(marker,'yes');
  }
  async function syncMenu() {
    // Attendre le menu IA de la semaine avant le premier enregistrement familial.
    if(window.MonPanierAIReady)await Promise.race([
      window.MonPanierAIReady,new Promise(resolve=>setTimeout(resolve,5000))
    ]);
    const data = await request(householdPath('/week-menus/' + week()));
    const remote = data.menu;
    if (remote) {
      if (adapter.menuDirty()) {
        session.message = '⚠ Un menu modifié sur cet appareil attend votre choix : publier ou recharger.';
        return;
      }
      if (adapter.applyMenu(remote)) session.menuVersion = Number(remote.version);
    } else {
      const payload = adapter.currentMenu();
      const response = await request(householdPath('/week-menus/' + week()),'PUT',
        {...payload,expected_version:0});
      session.menuVersion = Number(response.menu.version);
      adapter.markMenuSaved();
    }
  }
  async function publishMenu(confirmed=false) {
    if (!session.household || session.menuSaving) return;
    session.menuSaving = true;
    try {
      let expected = session.menuVersion;
      if (confirmed || expected == null) {
        const remote = await request(householdPath('/week-menus/' + week()));
        expected = Number(remote.menu?.version||0);
      }
      const result = await request(householdPath('/week-menus/' + week()),'PUT',
        {...adapter.currentMenu(),expected_version:expected});
      session.menuVersion = Number(result.menu.version);
      adapter.markMenuSaved();
      session.message = '✅ Menu de la semaine partagé avec la famille.';
    } catch (error) {
      session.message = '⚠ Menu local conservé : '+error.message+' (publiez-le ou rechargez le menu familial).';
    } finally { session.menuSaving = false; renderPanel(); }
  }
  function recordMenuChange() {
    if (!session.household || session.mode !== 'live' || session.menuVersion == null) return;
    void publishMenu(false);
  }
  async function discardMenu() {
    try {
      const data = await request(householdPath('/week-menus/' + week()));
      if (!data.menu || !adapter.applyMenu(data.menu)) throw new Error('Menu familial introuvable');
      session.menuVersion = Number(data.menu.version);
      session.message = 'Menu familial rechargé.';
    } catch (e) { session.message = '⚠ '+e.message; }
    renderPanel();
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
      loadProgressPending();
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
        try { await syncMenu(); } catch (e) { session.message = '⚠ Menu familial : '+e.message; }
        await snapshotAndApply();
        session.syncedWeek=week();
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
      localStorage.setItem(LINK_KEY,session.household.id);
      await syncExtras(action==='import');
      try { await syncMenu(); } catch (e) { session.message = '⚠ Menu familial : '+e.message; }
      await snapshotAndApply();
      session.syncedWeek=week();
      setMode('live', 'Synchronisation familiale activée.');
    } catch (error) {
      setMode('choose', error.message + ' Réessayez. Aucune donnée locale n’a été supprimée.');
    } finally { session.busy = false; }
  }
  function recordChange(key, removed) {
    if (session.mode !== 'live') return;
    if(session.syncedWeek && session.syncedWeek!==week()){
      if(session.queued.size){setMessage('⚠ Des achats de la semaine précédente restent à envoyer.');return;}
      session.syncedWeek=week();session.versions={};session.menuVersion=null;
      loadProgressPending();
      void syncMenu().catch(e=>setMessage(e.message));
    }
    const command = (removed ? 'delete:' : 'put:') + key;
    session.generations.set(command, (session.generations.get(command) || 0) + 1);
    session.queued.add(command);
    persistOutbox();
    void flush();
  }
  async function flush() {
    if(session.syncedWeek && session.syncedWeek!==week()){
      session.message='⚠ Envois de l’ancienne semaine à vérifier avant de continuer.';
      renderPanel();return;
    }
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
    if(session.syncedWeek && session.syncedWeek!==week()){
      if(session.queued.size){
        session.message='⚠ Des achats de l’ancienne semaine sont en attente. Aucune donnée n’est supprimée.';
        renderPanel();return;
      }
      session.syncedWeek=week();session.menuVersion=null;session.versions={};
      loadProgressPending();
      try{
        await syncExtras();await syncMenu();await snapshotAndApply();
        session.message='Nouvelle semaine synchronisée avec la famille.';
      }catch(e){session.message='⚠ Nouvelle semaine : '+e.message;}
      renderPanel();return;
    }
    if (!isLinked()) { setMode('choose', 'Nouvelle semaine : choisissez la liste familiale.'); return; }
    if (session.queued.size) { await flush(); return; }
    if (Object.keys(session.favoritePending).length) await flushFavorites();
    if (Object.keys(session.progressPending).length) await flushProgress();
    session.busy = true;
    try {
      const data = await request(householdPath('/events?after=' + session.lastEvent));
      if ((data.events || []).length) {
        if (data.events.some(e=>e.kind==='archive.saved')) await syncArchives();
        if (data.events.some(e=>e.kind==='weekly-menu.changed')) await syncMenu();
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
      keepSession(data);
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
      keepSession(data);
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
    const refreshToRevoke=session.refreshToken;
    if(refreshToRevoke) void fetch(API+'/api/session/logout',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({refresh_token:refreshToRevoke}),cache:'no-store'
    }).catch(()=>{});
    clearCredentials();
    session.household = null; session.profile = null;session.menuVersion=null;
    session.queued.clear(); session.generations.clear(); session.favoritePending={};session.progressPending={}; session.invitation = ''; session.lastEvent = 0;
    setMode('offline', 'Déconnecté. Les données déjà présentes sur cet appareil sont conservées.');
  }
  async function askPasswordReset(form) {
    const data=new FormData(form);
    try {
      const result=await request('/api/password-reset/request','POST',
        {email:String(data.get('email')||'')});
      setMessage(result.message||'Vérifie ta boîte e-mail.');
    }catch(e){setMessage(e.message);}
  }
  async function confirmPasswordReset(form) {
    const data=new FormData(form);
    const password=String(data.get('password')||'');
    if(password!==String(data.get('confirm')||'')){setMessage('Les deux mots de passe sont différents.');return;}
    try {
      await request('/api/password-reset/confirm','POST',{token:resetCode,new_password:password});
      resetCode=null;
      window.history.replaceState({},'',window.location.pathname+window.location.search);
      clearCredentials();
      setMode('offline','✅ Mot de passe modifié. Connecte-toi avec le nouveau.');
    }catch(e){setMessage(e.message);}
  }
  async function changePassword(form) {
    const data=new FormData(form),newPassword=String(data.get('new')||'');
    if(newPassword!==String(data.get('confirm')||'')){setMessage('Les deux mots de passe sont différents.');return;}
    try{
      await request('/api/password/change','POST',
        {current_password:String(data.get('current')||''),new_password:newPassword});
      logout();
      setMode('offline','✅ Mot de passe changé. Reconnecte-toi avec le nouveau.');
    }catch(e){setMessage(e.message);}
  }
  function renderPanel() {
    const target = document.getElementById('family-sync-panel');
    if (!target) return;
    let content = '<div class="card sheet" style="margin-bottom:16px"><h2 style="margin:0 0 8px">👨‍👩‍👧‍👦 Courses en famille</h2>';
    if (resetCode) {
      content += '<p>🔐 Choisis un nouveau mot de passe (12 caractères minimum).</p>'
        + '<form id="family-password-confirm" class="manual-add">'
        + '<input class="field" name="password" type="password" autocomplete="new-password" minlength="12" placeholder="Nouveau mot de passe" required>'
        + '<input class="field" name="confirm" type="password" autocomplete="new-password" minlength="12" placeholder="Confirmer le mot de passe" required>'
        + '<button class="btn" type="submit">Enregistrer mon nouveau mot de passe</button></form>';
    } else if (session.mode === 'offline' || session.mode === 'error') {
      content += '<p class="small">Connectez chaque téléphone à votre famille pour retrouver les coches en direct. Sans connexion, votre liste locale reste utilisable.</p>'
       + '<form id="family-login" class="manual-add" autocomplete="on"><input class="field" type="email" name="email" autocomplete="username" placeholder="Adresse e-mail" required>'
       + '<input class="field" type="password" name="password" autocomplete="current-password" placeholder="Mot de passe" required>'
       + '<button class="btn" type="submit">Se connecter</button></form>'
       + '<details style="margin-top:10px"><summary>Mot de passe oublié ?</summary>'
       + '<form id="family-password-request" class="manual-add" style="margin-top:10px">'
       + '<input class="field" type="email" name="email" autocomplete="email" placeholder="Adresse e-mail du compte" required>'
       + '<button class="btn btn-outline" type="submit">Recevoir un lien de récupération</button></form></details>'
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
          + '<p class="small">🔐 Connexion mémorisée sur cet appareil, renouvelée automatiquement.</p>'
          + '<div class="mini-links"><button class="btn btn-outline btn-small" data-family="refresh">🔄 Actualiser</button>'
          + '<button class="btn btn-outline btn-small" data-family="retry">Réessayer un envoi</button></div>';
      }
      if (session.mode === 'live' && adapter.menuDirty()) {
        content += '<div class="notice notice-amber"><b>Menu de la semaine modifié sur ce téléphone.</b>'
          + '<div class="mini-links"><button class="btn btn-small" data-family="publish-menu">Partager mon menu</button>'
          + '<button class="btn btn-small btn-outline" data-family="reload-menu">Recharger le menu familial</button></div></div>';
      }
      if (adapter.isAccountPage()) {
        content += '<details style="margin-top:12px"><summary>🔑 Changer mon mot de passe</summary>'
          + '<form id="family-password-change" class="manual-add" style="margin-top:10px">'
          + '<input class="field" name="current" type="password" autocomplete="current-password" placeholder="Mot de passe actuel" required>'
          + '<input class="field" name="new" type="password" autocomplete="new-password" minlength="12" placeholder="Nouveau mot de passe" required>'
          + '<input class="field" name="confirm" type="password" autocomplete="new-password" minlength="12" placeholder="Confirmer le nouveau mot de passe" required>'
          + '<button class="btn" type="submit">Changer le mot de passe</button></form></details>';
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
    if (event.target.id === 'family-password-request') { event.preventDefault(); void askPasswordReset(event.target); }
    if (event.target.id === 'family-password-confirm') { event.preventDefault(); void confirmPasswordReset(event.target); }
    if (event.target.id === 'family-password-change') { event.preventDefault(); void changePassword(event.target); }
  });
  document.addEventListener('click', event => {
    const button = event.target.closest('[data-family]');
    if (!button) return;
    const action = button.dataset.family;
    if (action === 'receive') void link('receive');
    if (action === 'import') void link('import');
    if (action === 'refresh') void snapshotAndApply().catch(e => setMessage(e.message));
    if (action === 'retry') { void flush(); void flushFavorites(); void flushProgress(); void syncArchives().catch(e=>setMessage(e.message)); }
    if (action === 'invite') void invitation();
    if (action === 'logout') logout();
    if (action === 'publish-menu' && window.confirm('Partager ce menu avec toute la famille ?')) void publishMenu(true);
    if (action === 'reload-menu' && window.confirm('Remplacer le menu local par celui de la famille ?')) void discardMenu();
    if (action === 'copy-invite' && session.invitation) {
      if (navigator.clipboard?.writeText) void navigator.clipboard.writeText(session.invitation);
      else window.prompt('Copiez le code :', session.invitation);
    }
  });

  window.MonPanierFamily = { renderPanel, recordChange, setFavorite, archiveWeek, recordMenuChange, recordRecipeDone };
  window.addEventListener('mon-panier:render', renderPanel);
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') void poll(); });
  setInterval(() => { void poll(); }, 8000);
  renderPanel();
  if (resetCode) renderPanel();
  else if (session.token || session.refreshToken) void (async()=>{
    try { if(session.refreshToken) await refreshAccess(); await start(); }
    catch(e) { setMode('offline',e.message); }
  })();
})();