const rows = document.querySelector('#patient-rows');
const empty = document.querySelector('#empty-state');
const notice = document.querySelector('#notice');
const dialog = document.querySelector('#patient-dialog');
const form = document.querySelector('#patient-form');
let patients = [];

const formatPhone = value => value ? `(${value.slice(0,3)}) ${value.slice(3,6)}-${value.slice(6)}` : '—';
const formatDate = value => value ? new Intl.DateTimeFormat('en-US', {timeZone: 'UTC'}).format(new Date(`${value}T00:00:00Z`)) : '—';
const showNotice = (message, isError = false) => {
  notice.textContent = message;
  notice.classList.toggle('error', isError);
  notice.hidden = false;
  window.setTimeout(() => { notice.hidden = true; }, 5000);
};

async function api(path, options = {}) {
  const response = await fetch(path, {headers: {'Content-Type': 'application/json'}, ...options});
  const body = await response.json();
  if (!response.ok) throw new Error(body.error?.details?.map(x => `${x.field}: ${x.message}`).join('; ') || body.error?.message || 'Request failed');
  return body.data;
}

function render() {
  rows.replaceChildren();
  empty.hidden = patients.length !== 0;
  for (const patient of patients) {
    const tr = document.createElement('tr');
    const cells = [
      [`${patient.first_name} ${patient.last_name}`, patient.patient_id.slice(0, 8)],
      [formatDate(patient.date_of_birth), patient.sex],
      [formatPhone(patient.phone_number), patient.email || 'No email'],
      [`${patient.city}, ${patient.state}`, patient.zip_code],
      [formatDate(patient.created_at.slice(0, 10)), ''],
    ];
    for (const [primary, secondary] of cells) {
      const td = document.createElement('td');
      const strong = document.createElement('strong'); strong.textContent = primary; td.append(strong);
      if (secondary) { const small = document.createElement('small'); small.textContent = secondary; td.append(small); }
      tr.append(td);
    }
    const actions = document.createElement('td'); actions.className = 'row-actions';
    const edit = document.createElement('button'); edit.type = 'button'; edit.textContent = 'Edit'; edit.addEventListener('click', () => openEdit(patient));
    const remove = document.createElement('button'); remove.type = 'button'; remove.textContent = 'Delete'; remove.className = 'delete'; remove.addEventListener('click', () => removePatient(patient));
    actions.append(edit, remove); tr.append(actions); rows.append(tr);
  }
}

async function loadPatients(params = new URLSearchParams()) {
  try {
    const data = await api(`/patients?${params}`);
    patients = data.items;
    document.querySelector('#patient-total').textContent = data.total;
    document.querySelector('#result-count').textContent = `${data.total} record${data.total === 1 ? '' : 's'}`;
    render();
  } catch (error) { showNotice(error.message, true); }
}

function openEdit(patient = null) {
  form.reset();
  document.querySelector('#form-error').hidden = true;
  document.querySelector('#dialog-title').textContent = patient ? 'Edit patient' : 'Add patient';
  document.querySelector('#patient-id').value = patient?.patient_id || '';
  form.elements.preferred_language.value = patient?.preferred_language || 'English';
  if (patient) Object.entries(patient).forEach(([key, value]) => { if (form.elements[key] && value != null) form.elements[key].value = value; });
  dialog.showModal();
}

form.addEventListener('submit', async event => {
  event.preventDefault();
  const id = document.querySelector('#patient-id').value;
  const payload = Object.fromEntries(new FormData(form));
  Object.keys(payload).forEach(key => { if (payload[key] === '') delete payload[key]; });
  try {
    await api(id ? `/patients/${id}` : '/patients', {method: id ? 'PUT' : 'POST', body: JSON.stringify(payload)});
    dialog.close(); showNotice(id ? 'Patient updated.' : 'Patient added.'); await loadPatients();
  } catch (error) { const box = document.querySelector('#form-error'); box.textContent = error.message; box.hidden = false; }
});

async function removePatient(patient) {
  if (!window.confirm(`Soft-delete ${patient.first_name} ${patient.last_name}?`)) return;
  try { await api(`/patients/${patient.patient_id}`, {method: 'DELETE'}); showNotice('Patient removed.'); await loadPatients(); }
  catch (error) { showNotice(error.message, true); }
}

document.querySelector('#search-form').addEventListener('submit', event => {
  event.preventDefault();
  const params = new URLSearchParams(new FormData(event.currentTarget));
  for (const [key, value] of [...params]) if (!value) params.delete(key);
  loadPatients(params);
});
document.querySelector('#clear-search').addEventListener('click', () => { document.querySelector('#search-form').reset(); loadPatients(); });
document.querySelector('#add-patient').addEventListener('click', () => openEdit());
document.querySelectorAll('[data-close]').forEach(button => button.addEventListener('click', () => dialog.close()));

api('/health').then(() => { const status = document.querySelector('#service-status'); status.textContent = 'Service online'; status.classList.add('online'); }).catch(() => {});
loadPatients();
