import { h } from 'preact';
import { html } from 'htm/preact';
import { useEffect, useState } from 'preact/hooks';
import { marked } from 'marked';

function ManualView() {
  const [chapters, setChapters] = useState([]);
  const [active, setActive] = useState(null);
  const [content, setContent] = useState("");
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch("/api/manual")
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((manifest) => {
        const items = manifest.chapters || [];
        setChapters(items);
        setActive(items[0] || null);
      })
      .catch(() => setError("無法載入使用手冊目錄。"));
  }, []);

  useEffect(() => {
    if (!active) return;
    setError(null);
    setContent("");
    if (active.status === "stub") {
      return;
    }
    fetch(`/api/manual/${active.slug}`)
      .then((r) => (r.ok ? r.text() : Promise.reject(r.status)))
      // ponytail: repo-authored markdown is trusted; add sanitizer if users can edit it.
      .then((markdown) => setContent(marked.parse(markdown)))
      .catch(() => setError(`無法載入章節：${active.title}`));
  }, [active]);

  return html`
    <div class="row" style=${{ gap: "var(--gap-lg)", alignItems: "flex-start" }}>
      <aside class="card" style=${{ minWidth: 220, maxWidth: 260 }}>
        <div class="card-title" style=${{ marginBottom: 8 }}>章節</div>
        ${chapters.map((chapter) => html`
          <div
            key=${chapter.slug}
            class="nav-item"
            aria-current=${active?.slug === chapter.slug ? "page" : undefined}
            onClick=${() => setActive(chapter)}
          >
            <span>${chapter.title}</span>
            ${chapter.status === "stub" && html`<span class="chip" style=${{ marginLeft: "auto" }}>待補</span>`}
          </div>
        `)}
      </aside>

      <section class="card" style=${{ flex: 1 }}>
        ${error && html`<div style=${{ color: "var(--loss)" }}>${error}</div>`}
        ${!error && !active && html`<div style=${{ color: "var(--text-muted)" }}>尚無章節。</div>`}
        ${!error && active?.status === "stub" && html`
          <div class="col" style=${{ gap: 8 }}>
            <div class="card-title">${active.title}</div>
            <div style=${{ color: "var(--text-muted)" }}>待補。請先參考相關 source docs。</div>
          </div>
        `}
        ${!error && active && active.status !== "stub" && html`
          <div class="manual-content" dangerouslySetInnerHTML=${{ __html: content }}></div>
        `}
      </section>
    </div>
  `;
}

window.ManualView = ManualView;
