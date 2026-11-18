// Small shared interactions; the application does not depend on a frontend framework.
document.addEventListener('click', (event) => {
  const dismiss = event.target.closest('[data-dismiss]');
  if (dismiss) dismiss.closest('.flash')?.remove();
});
