document.addEventListener('DOMContentLoaded', () => {
  const runSummary = document.getElementById('run-summary');

  // --- helpers ---------------------------------------------------------------
  const setBtnBusy = (btn, text = 'Working...') => {
    if (!btn) return () => {};
    const original = btn.textContent;
    btn.disabled = true;
    btn.textContent = text;
    return () => { btn.disabled = false; btn.textContent = original; };
  };

  const flash = (kind, html) => {
    // kind: 'success' | 'warning' | 'danger' | 'info'
    if (!runSummary) return;
    runSummary.innerHTML = `
      <div class="alert alert-${kind} alert-dismissible fade show" role="alert">
        ${html}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
      </div>`;
    runSummary.scrollIntoView({ behavior: 'smooth' });
  };

  const okOrThrow = async (res) => {
    if (res.ok) return res;
    // Try to pull a message from JSON or text
    const ct = res.headers.get('Content-Type') || '';
    let msg = `${res.status} ${res.statusText}`;
    try {
      if (ct.includes('application/json')) {
        const j = await res.json();
        msg = j.error || j.message || (Array.isArray(j.errors) ? j.errors.join(', ') : JSON.stringify(j));
      } else {
        msg = await res.text();
      }
    } catch (_) {}
    throw new Error(msg);
  };

  const renderRunSuccess = (label, data) => {
    const valueErrors = Array.isArray(data["Value errors"])
      ? data["Value errors"].length
      : data["Value errors"];
    const html = `
      <strong>${label} Summary</strong><br>
      Value fallbacks: ${data["Value fallbacks"]}<br>
      Bound warnings: ${data["Bound warnings"]}<br>
      Value errors: ${valueErrors}<br>
      Values ignored: ${data["Values ignored"]}<br>
      Values imported: ${data["Values imported"]}<br>
      Values missing: ${data["Values missing"]}<br>
      Values imputed: ${data["Values imputed"]}<br>
      Duration: ${data["Duration"]}
    `;
    flash('success', html);
  };

  // --- delegated submits -----------------------------------------------------
  document.addEventListener('submit', async (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) return;

    // 1) ANALYZE → poll until done, then download CSV
    if (form.matches('form.analyze-form')) {
      event.preventDefault();
      const btn = event.submitter;
      const done = setBtnBusy(btn, 'Analyzing...');

      try {
        const res = await fetch(form.action, {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'X-Requested-With': 'XMLHttpRequest' }
        }).then(okOrThrow);

        const data = await res.json();

        if (!data.polling || !data.job_id) {
          flash('danger', data.errors ? data.errors.join(', ') : 'Analyze failed');
          done();
          return;
        }

        const jobId = data.job_id;
        const poll = async () => {
          try {
            const sr = await fetch(`/api/minmax-analysis-status/${jobId}`, { credentials: 'same-origin' });
            const status = await sr.json();

            if (status.status === 'running') {
              setTimeout(poll, 5000);
              return;
            }

            done();

            if (status.status === 'error') {
              flash('danger', `Analyze error: ${status.message}`);
              return;
            }

            // Done — fetch and download the CSV
            const csvRes = await fetch(`/api/minmax-analysis-result/${jobId}`, { credentials: 'same-origin' });
            if (!csvRes.ok) {
              flash('danger', 'Failed to retrieve analysis result.');
              return;
            }
            const cd = csvRes.headers.get('Content-Disposition') || '';
            const match = /filename\*=UTF-8''([^;]+)|filename="?([^"]+)"?/i.exec(cd);
            const filename = decodeURIComponent((match && (match[1] || match[2])) || 'analysis.csv');
            const blob = await csvRes.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url; a.download = filename;
            document.body.appendChild(a); a.click(); a.remove();
            URL.revokeObjectURL(url);
            flash('success', `Your analysis file <code>${filename}</code> has been downloaded.`);
          } catch (err) {
            done();
            flash('danger', `Analyze error: ${err.message}`);
          }
        };
        poll();
      } catch (err) {
        done();
        flash('danger', `Analyze error: ${err.message}`);
      }
      return;
    }

    // 2) RUN STAGE → poll until done, then show summary
    if (form.matches('form.run-stage-form')) {
      event.preventDefault();
      const label = (event.submitter && event.submitter.textContent) ? event.submitter.textContent.trim() : 'Run';
      const btn = event.submitter;
      const done = setBtnBusy(btn, 'Running...');

      try {
        const res = await fetch(form.action, {
          method: 'POST',
          headers: { 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json' },
          credentials: 'same-origin'
        }).then(okOrThrow);

        const data = await res.json();

        if (!data.polling || !data.job_id) {
          done();
          const errs = Array.isArray(data.errors) ? data.errors.join(', ') : (data.errors || 'Unknown error');
          flash('danger', errs);
          return;
        }

        const jobId = data.job_id;
        const poll = async () => {
          try {
            const sr = await fetch(`/api/run-minmax-stage-status/${jobId}`, { credentials: 'same-origin' });
            const status = await sr.json();

            if (status.status === 'running') {
              setTimeout(poll, 5000);
              return;
            }

            done();

            if (status.status === 'error') {
              flash('danger', `Run error: ${status.message}`);
              return;
            }

            renderRunSuccess(label, status);
          } catch (err) {
            done();
            flash('danger', `Run error: ${err.message}`);
          }
        };
        poll();
      } catch (err) {
        done();
        flash('danger', `Run error: ${err.message}`);
      }
    }
  });
});
