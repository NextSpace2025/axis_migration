(() => {
  const login=document.querySelector('.operator-login');
  if(!login) return;
  fetch('/login?status',{cache:'no-store'}).then(r=>r.ok?r.json():null).then(state=>{
    if(!state?.loggedIn) return;
    const form=document.createElement('form');
    form.method='post'; form.action='/login'; form.className='operator-login';
    const button=document.createElement('button');
    button.type='submit';button.name='action';button.value='logout';button.textContent='로그아웃';
    form.append(button);login.replaceWith(form);
  }).catch(()=>{});
})();
