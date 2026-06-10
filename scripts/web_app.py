#!/usr/bin/env python3
import html
import argparse
import gzip
import json
import re
import shutil
import shlex
import subprocess
import threading
import time
import uuid
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[1]
UPLOAD_ROOT = ROOT / "data" / "web_uploads"
PROJECT_ROOT = ROOT / "projects"
RESULT_ROOT = ROOT / "results"
PIPELINE = ROOT / "scripts" / "shape_map_local.py"
JOBS = {}


INDEX_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>SHAPE-MaP Local Runner</title>
  <style>
    :root { color-scheme: light; --line:#d7dde8; --ink:#18202f; --muted:#667085; --brand:#2563eb; --bg:#f7f9fc; --panel:#fff; }
    * { box-sizing: border-box; }
    body { margin:0; font-family: "Segoe UI", Arial, sans-serif; background:var(--bg); color:var(--ink); }
    header { padding:20px 28px 16px; border-bottom:1px solid var(--line); background:#fff; position:sticky; top:0; z-index:2; }
    h1 { margin:0 0 6px; font-size:24px; }
    .sub { color:var(--muted); font-size:14px; }
    main { max-width:1180px; margin:0 auto; padding:22px; display:grid; grid-template-columns: minmax(0, 1fr) 360px; gap:18px; }
    section, aside { background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:18px; }
    h2 { margin:0 0 14px; font-size:17px; }
    h3 { margin:20px 0 10px; font-size:15px; }
    .title-row { display:flex; align-items:center; justify-content:space-between; gap:12px; }
    .help-btn {
      width:28px;
      height:28px;
      border-radius:50%;
      padding:0;
      display:inline-flex;
      align-items:center;
      justify-content:center;
      font-size:19px;
      font-weight:700;
      background:#0b8bdc;
      color:#fff;
    }
    label { display:block; font-size:13px; font-weight:600; margin:12px 0 6px; }
    input, textarea, select { width:100%; border:1px solid #cbd5e1; border-radius:6px; padding:9px 10px; font-size:14px; background:#fff; }
    textarea { min-height:76px; resize:vertical; font-family: Consolas, monospace; }
    input[type=file] { padding:8px; }
    .grid { display:grid; grid-template-columns: 1fr 1fr; gap:12px; }
    .sample { border:1px solid var(--line); border-radius:8px; padding:12px; margin:10px 0; background:#fbfcff; }
    .group-card { border:1px solid var(--line); border-radius:8px; padding:14px; margin:12px 0; background:#fff; }
    .group-head { display:grid; grid-template-columns:minmax(0, 1fr) auto; gap:10px; align-items:end; }
    .role-title { display:flex; align-items:center; justify-content:space-between; gap:10px; margin-bottom:6px; font-weight:700; }
    .hint { color:var(--muted); font-size:12px; margin-top:5px; line-height:1.45; }
    .row { display:flex; gap:10px; align-items:center; flex-wrap:wrap; }
    .check { display:flex; gap:8px; align-items:center; margin-top:12px; font-size:13px; }
    .check input { width:auto; }
    button { background:var(--brand); color:#fff; border:0; border-radius:6px; padding:10px 14px; font-size:14px; cursor:pointer; }
    button.secondary { background:#334155; }
    button.small { padding:7px 10px; font-size:12px; }
    button.danger { background:#b42318; }
    button:disabled { opacity:.6; cursor:not-allowed; }
    .mode { display:grid; grid-template-columns:1fr 1fr 1fr; gap:8px; margin-bottom:10px; }
    .mode label { margin:0; border:1px solid var(--line); padding:9px; border-radius:6px; font-weight:500; cursor:pointer; }
    .mode input { width:auto; margin-right:6px; }
    pre { white-space:pre-wrap; overflow:auto; background:#0f172a; color:#e2e8f0; border-radius:8px; padding:12px; min-height:280px; max-height:560px; font-size:12px; line-height:1.45; }
    .status { border:1px solid var(--line); border-radius:8px; padding:10px; margin-bottom:12px; background:#fbfcff; }
    .pill { display:inline-block; padding:3px 8px; border-radius:999px; background:#e2e8f0; font-size:12px; }
    .result { border:1px solid var(--line); border-radius:8px; padding:12px; margin-bottom:12px; background:#fff; font-size:13px; line-height:1.5; }
    .result table { width:100%; border-collapse:collapse; margin-top:8px; }
    .result th, .result td { border-bottom:1px solid #e5e7eb; padding:5px 2px; text-align:left; }
    .warn { color:#b45309; font-weight:600; }
    .ok { color:#047857; font-weight:600; }
    .hidden { display:none; }
    dialog {
      border:0;
      border-radius:8px;
      width:min(720px, calc(100vw - 32px));
      padding:0;
      box-shadow:0 18px 60px rgba(15,23,42,.28);
    }
    dialog::backdrop { background:rgba(15,23,42,.35); }
    .modal-head {
      display:flex;
      justify-content:space-between;
      align-items:center;
      padding:16px 18px;
      border-bottom:1px solid var(--line);
    }
    .modal-head h2 { margin:0; }
    .modal-body { padding:16px 18px 20px; color:#344054; line-height:1.6; font-size:14px; }
    .modal-body h3 { margin:14px 0 6px; color:#172033; }
    .modal-body ul { margin:6px 0 12px; padding-left:20px; }
    .close-btn { background:#475569; }
    @media (max-width: 920px) { main { grid-template-columns:1fr; } }
  </style>
</head>
<body>
  <header>
    <h1>SHAPE-MaP Local Runner</h1>
    <div class="sub">本地上传/选择文件，自动拆分 mixed FASTQ，必要时拼接参考序列，然后运行 ShapeMapper2。</div>
  </header>
  <main>
    <section>
      <h2>新建分析</h2>
      <form id="runForm">
        <div class="grid">
          <div>
            <label>项目名</label>
            <input name="project_name" value="shape_map_project" required />
          </div>
          <div>
            <label>运行模式</label>
            <select name="run_mode">
              <option value="full">拆分样本并运行 ShapeMapper2</option>
              <option value="demux">只按引物拆分样本</option>
              <option value="assemble">只拼接参考序列</option>
            </select>
          </div>
        </div>
        <label>输出结果存放路径，可选</label>
        <input name="output_dir" placeholder="留空则使用 results/项目名；也可填写 D:\\shape-map-results\\project1 或 ../results/project1" />
        <div class="hint">拆分后的 FASTQ、ShapeMapper2 输出、运行摘要都会保存在这里。不要填写系统目录；建议使用空间充足的磁盘。</div>

        <h3>测序文件</h3>
        <div class="grid">
          <div>
            <label>混合 FASTQ R1 上传</label>
            <input type="file" name="r1_file" />
            <div class="hint">也可以不上传，在下面填写本地/WSL 路径。</div>
          </div>
          <div>
            <label>混合 FASTQ R2 上传</label>
            <input type="file" name="r2_file" />
          </div>
        </div>
        <div class="grid">
          <div>
            <label>R1 已有路径</label>
            <input name="r1_path" placeholder="../data/raw/mixed_R1.fastq.gz" />
          </div>
          <div>
            <label>R2 已有路径</label>
            <input name="r2_path" placeholder="../data/raw/mixed_R2.fastq.gz" />
          </div>
        </div>

        <h3>参考序列</h3>
        <div class="mode">
          <label><input type="radio" name="ref_mode" value="target" checked />完整 FASTA</label>
          <label><input type="radio" name="ref_mode" value="assemble" />片段拼接</label>
          <label><input type="radio" name="ref_mode" value="existing" />已有路径</label>
        </div>
        <div id="targetRef">
          <label>完整参考 FASTA 上传</label>
          <input type="file" name="target_file" />
        </div>
        <div id="assembleRef" class="hidden">
          <label>片段 FASTA 上传</label>
          <input type="file" name="fragments_file" />
          <div class="grid">
            <div>
              <label>拼接后序列名</label>
              <input name="assembled_name" value="full_target" />
            </div>
            <div>
              <label>最小重叠长度</label>
              <input name="min_overlap" type="number" value="20" min="1" />
            </div>
          </div>
          <label>片段顺序，可选</label>
          <textarea name="fragment_order" placeholder="fragment_001&#10;fragment_002&#10;fragment_003"></textarea>
        </div>
        <div id="existingRef" class="hidden">
          <label>参考 FASTA 已有路径</label>
          <input name="target_path" placeholder="../data/target.fa" />
        </div>

        <div class="title-row">
          <h3>按引物拆分样本</h3>
          <button class="help-btn" type="button" data-help="demux" title="查看拆分参数说明">?</button>
        </div>
        <input type="hidden" name="sample_groups_json" id="sampleGroupsJson" />
        <div id="sampleGroups"></div>
        <div class="row">
          <button class="secondary" type="button" id="addGroupBtn">添加一套样本组</button>
        </div>
        <div class="hint">每一套样本组代表一个可以独立分析的对象，例如 RNA1、RNA2。每套组至少需要 Modified 和 Untreated；Denatured 可以留空。</div>
        <div class="grid">
          <div>
            <label>搜索 read 前多少 bp</label>
            <input name="search_bases" type="number" value="40" min="1" />
          </div>
          <div>
            <label>允许错配数</label>
            <input name="max_mismatches" type="number" value="1" min="0" />
          </div>
        </div>
        <div class="check"><input type="checkbox" name="anchored" />只允许在 read 开头匹配</div>
        <div class="check"><input type="checkbox" name="check_reverse_complement" />同时检查反向互补序列</div>

        <div class="title-row">
          <h3>ShapeMapper2 参数</h3>
          <button class="help-btn" type="button" data-help="shape" title="查看 ShapeMapper2 参数说明">?</button>
        </div>
        <div class="grid">
          <div><label>min depth</label><input name="min_depth" type="number" value="1000" /></div>
          <div><label>CPU 核心数</label><input name="nproc" type="number" value="4" /></div>
          <div><label>min mapq</label><input name="min_mapq" type="number" value="10" /></div>
          <div><label>max bg</label><input name="max_bg" type="number" step="0.01" value="0.05" /></div>
        </div>
        <div class="check"><input type="checkbox" name="amplicon" checked />使用 amplicon 模式</div>
        <label>ShapeMapper2 primers 文件，可选</label>
        <input type="file" name="primers_file" />
        <div class="hint">如果是很多 300 bp tiled amplicons，建议提供这个文件，让 ShapeMapper2 知道每对扩增引物的位置。</div>

        <h3>示例数据试跑</h3>
        <label>官方示例数据路径，可选</label>
        <input name="example_path" id="examplePath" placeholder="留空则使用 ~/tools/shapemapper2-2.3/example_data" />
        <label>官方示例输出路径，可选</label>
        <input name="example_output_dir" id="exampleOutputDir" placeholder="留空则使用 results/official_tpp_example_..." />
        <div class="hint">可以填写 Windows 路径、WSL 路径，或留空使用 ShapeMapper2 自带 TPP 示例数据。</div>

        <div class="row" style="margin-top:18px">
          <button id="submitBtn" type="submit">开始</button>
          <button class="secondary" type="button" id="exampleBtn">运行官方示例</button>
          <button class="secondary" type="button" id="refreshBtn">刷新日志</button>
        </div>
      </form>
    </section>
    <aside>
      <h2>运行状态</h2>
      <div class="status">
        <div>Job: <span id="jobId" class="pill">尚未开始</span></div>
        <div style="margin-top:8px">Status: <span id="jobStatus" class="pill">idle</span></div>
      </div>
      <div id="resultBox" class="result">结果摘要会显示在这里。</div>
      <pre id="logBox">等待提交任务...</pre>
    </aside>
  </main>
  <dialog id="helpDialog">
    <div class="modal-head">
      <h2 id="helpTitle">参数说明</h2>
      <button class="close-btn" type="button" id="helpClose">关闭</button>
    </div>
    <div class="modal-body" id="helpBody"></div>
  </dialog>
  <script>
    const form = document.getElementById('runForm');
    const logBox = document.getElementById('logBox');
    const resultBox = document.getElementById('resultBox');
    const jobIdEl = document.getElementById('jobId');
    const jobStatusEl = document.getElementById('jobStatus');
    let currentJob = null;
    let timer = null;
    const helpDialog = document.getElementById('helpDialog');
    const helpTitle = document.getElementById('helpTitle');
    const helpBody = document.getElementById('helpBody');
    const sampleGroupsEl = document.getElementById('sampleGroups');
    const sampleGroupsJson = document.getElementById('sampleGroupsJson');
    let groupCounter = 0;
    const roleLabels = {
      modified: 'Modified / 修饰后',
      untreated: 'Untreated / 未处理',
      denatured: 'Denatured / 变性，可选'
    };

    function escapeAttr(value) {
      return String(value ?? '').replace(/[&<>"']/g, (ch) => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
      }[ch]));
    }

    function roleBlock(role, defaults = {}) {
      return `
        <div class="sample" data-role="${role}">
          <div class="role-title"><span>${roleLabels[role]}</span></div>
          <label>样本显示名称</label>
          <input class="sample-name" value="${escapeAttr(defaults.name || role)}" />
          <div class="grid">
            <div><label>R1 识别序列</label><textarea class="sample-r1">${escapeAttr(defaults.r1 || '')}</textarea></div>
            <div><label>R2 识别序列</label><textarea class="sample-r2">${escapeAttr(defaults.r2 || '')}</textarea></div>
          </div>
          ${role === 'denatured' ? '<div class="hint">没有 denatured 时，这一行可以完全留空。</div>' : ''}
        </div>
      `;
    }

    function addSampleGroup(defaults = {}) {
      groupCounter += 1;
      const groupName = defaults.group_name || `group${groupCounter}`;
      const samples = defaults.samples || {};
      const card = document.createElement('div');
      card.className = 'group-card';
      card.innerHTML = `
        <div class="group-head">
          <div>
            <label>样本套组名称</label>
            <input class="group-name" value="${escapeAttr(groupName)}" placeholder="例如 RNA1 或 amplicon_01" />
          </div>
          <button class="danger small remove-group" type="button">删除这套</button>
        </div>
        ${roleBlock('modified', samples.modified || {name: 'modified'})}
        ${roleBlock('untreated', samples.untreated || {name: 'untreated'})}
        ${roleBlock('denatured', samples.denatured || {name: 'denatured'})}
      `;
      card.querySelector('.remove-group').addEventListener('click', () => {
        if (document.querySelectorAll('.group-card').length <= 1) {
          alert('至少保留一套样本组。');
          return;
        }
        card.remove();
      });
      sampleGroupsEl.appendChild(card);
    }

    function collectSampleGroups() {
      const groups = [];
      document.querySelectorAll('.group-card').forEach((card, index) => {
        const groupName = card.querySelector('.group-name').value.trim() || `group${index + 1}`;
        const samples = [];
        card.querySelectorAll('.sample[data-role]').forEach((sampleEl) => {
          const role = sampleEl.dataset.role;
          const name = sampleEl.querySelector('.sample-name').value.trim() || role;
          const r1 = sampleEl.querySelector('.sample-r1').value.trim();
          const r2 = sampleEl.querySelector('.sample-r2').value.trim();
          if (r1 || r2) {
            samples.push({ role, name, r1, r2 });
          }
        });
        if (samples.length) {
          groups.push({ group_name: groupName, samples });
        }
      });
      sampleGroupsJson.value = JSON.stringify(groups);
      return groups;
    }

    document.getElementById('addGroupBtn').addEventListener('click', () => addSampleGroup());
    addSampleGroup({
      group_name: 'group1',
      samples: {
        modified: {name: 'modified'},
        untreated: {name: 'untreated'},
        denatured: {name: 'denatured'}
      }
    });

    const helpText = {
      demux: {
        title: '按 barcode/引物拆分样本怎么调',
        body: `
          <h3>短 barcode，6-8 bp，位于 read 5' 端</h3>
          <ul>
            <li>搜索 read 前多少 bp：8 或 10</li>
            <li>允许错配数：0</li>
            <li>只允许在 read 开头匹配：勾选</li>
            <li>同时检查反向互补序列：通常不勾选</li>
          </ul>
          <h3>barcode 前面有 UMI/random bases</h3>
          <ul>
            <li>搜索 read 前多少 bp：12-20</li>
            <li>允许错配数：0</li>
            <li>只允许在 read 开头匹配：不勾选</li>
          </ul>
          <h3>不确定 barcode 在 R1 还是 R2</h3>
          <ul>
            <li>先把 barcode 分别填到 R1 或 R2 试运行“只按引物拆分样本”。</li>
            <li>看 modified / untreated / denatured 三组 reads 是否都能拆出来。</li>
            <li>如果某组为 0，优先检查 barcode 方向、样本文件是否选错、公司是否已经按 index 拆过样本。</li>
          </ul>
          <h3>样本显示名称</h3>
          <ul>
            <li>每一套样本组都可以独立命名，例如 RNA1、RNA2、amplicon_01。</li>
            <li>每套组内部仍然使用 modified / untreated / denatured 三个角色；样本显示名称可以按实验命名，例如 RNA1-plus、RNA1-minus。</li>
            <li>如果某套组没有 denatured 样本，denatured 这一行可以留空，程序会按 modified + untreated 两样本模式运行。</li>
          </ul>
          <h3>填写格式示例</h3>
          <ul>
            <li>单个 barcode：<code>TAGCTTGT</code></li>
            <li>多个候选 barcode：每行一个，例如 <code>TAGCTTGT</code>、<code>TAGCTTGC</code></li>
            <li>R1 有 barcode、R2 没有：只填 R1 识别序列，R2 留空。</li>
            <li>样本套组名称：<code>RNA1</code>、<code>RNA2</code>、<code>fragment_set_01</code></li>
            <li>样本显示名称：<code>sample-plus</code>、<code>sample-minus</code>、<code>sample-denatured</code></li>
          </ul>
        `
      },
      shape: {
        title: 'ShapeMapper2 参数怎么选',
        body: `
          <h3>常规三样本 SHAPE-MaP</h3>
          <ul>
            <li>modified、untreated 至少要有 reads；denatured 强烈推荐。</li>
            <li>没有 denatured 时也可以运行，但归一化和质控信息会少一些。</li>
            <li>min-depth：预分析 1000，正式分析 2000，深度很高可用 5000。</li>
            <li>min-mapq：建议 10，不要轻易调高。</li>
            <li>max-bg：建议 0.05。</li>
          </ul>
          <h3>短 RNA 或单个 amplicon</h3>
          <ul>
            <li>amplicon：建议勾选。</li>
            <li>如果只有一对引物，参考 FASTA 中 primer-binding 区域可用小写标记。</li>
          </ul>
          <h3>很多 300 bp tiled amplicons</h3>
          <ul>
            <li>amplicon：建议勾选。</li>
            <li>建议上传 ShapeMapper2 primers 文件，每行一对 forward/reverse primer。</li>
            <li>如果参考序列由多个片段组成，可先用“片段拼接”生成完整 target。</li>
          </ul>
          <h3>电脑性能</h3>
          <ul>
            <li>8 核电脑：nproc 可设 4 或 6。</li>
            <li>12 核电脑：nproc 可设 8。</li>
            <li>不要把全部核心都给分析程序，Windows 和 WSL 也需要资源。</li>
          </ul>
          <h3>填写格式示例</h3>
          <ul>
            <li>已有 FASTQ 路径：<code>../data/raw/sample_R1.fq.gz</code></li>
            <li>Windows 绝对路径：<code>C:\\Users\\YourName\\Desktop\\sample_R1.fq.gz</code>，不要加引号。</li>
            <li>片段顺序：每行一个 FASTA header，例如 <code>fragment_001</code>、<code>fragment_002</code>。</li>
            <li>primers 文件：每行一对引物，例如 <code>ATGCTAGC CGATCGAT</code>。</li>
          </ul>
        `
      }
    };

    document.querySelectorAll('[data-help]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const item = helpText[btn.dataset.help];
        helpTitle.textContent = item.title;
        helpBody.innerHTML = item.body;
        helpDialog.showModal();
      });
    });
    document.getElementById('helpClose').addEventListener('click', () => helpDialog.close());

    function syncRefMode() {
      const mode = new FormData(form).get('ref_mode');
      document.getElementById('targetRef').classList.toggle('hidden', mode !== 'target');
      document.getElementById('assembleRef').classList.toggle('hidden', mode !== 'assemble');
      document.getElementById('existingRef').classList.toggle('hidden', mode !== 'existing');
    }
    form.querySelectorAll('input[name=ref_mode]').forEach(x => x.addEventListener('change', syncRefMode));
    syncRefMode();

    function renderResult(data) {
      if (!data.result) {
        resultBox.innerHTML = '结果摘要会显示在这里。';
        return;
      }
      const r = data.result;
      let html = `<div><strong>结论：</strong> <span class="${r.level === 'ok' ? 'ok' : 'warn'}">${r.title}</span></div>`;
      html += `<div>${r.message || ''}</div>`;
      if (r.demux && r.demux.roles) {
        html += '<table><thead><tr><th>分组</th><th>reads</th></tr></thead><tbody>';
        for (const role of ['modified','untreated','denatured']) {
          html += `<tr><td>${role}</td><td>${r.demux.roles[role] ?? 0}</td></tr>`;
        }
        html += `<tr><td>unmatched</td><td>${r.demux.unmatched ?? 0}</td></tr>`;
        html += `<tr><td>ambiguous</td><td>${r.demux.ambiguous ?? 0}</td></tr>`;
        html += '</tbody></table>';
        if (r.demux.samples) {
          html += '<table><thead><tr><th>样本名称</th><th>reads</th></tr></thead><tbody>';
          for (const [name, count] of Object.entries(r.demux.samples)) {
            html += `<tr><td>${name}</td><td>${count}</td></tr>`;
          }
          html += '</tbody></table>';
        }
        if (r.demux.groups) {
          html += '<table><thead><tr><th>样本套组</th><th>modified</th><th>untreated</th><th>denatured</th></tr></thead><tbody>';
          for (const [groupName, groupData] of Object.entries(r.demux.groups)) {
            const roles = groupData.roles || {};
            html += `<tr><td>${groupName}</td><td>${roles.modified ?? 0}</td><td>${roles.untreated ?? 0}</td><td>${roles.denatured ?? 0}</td></tr>`;
          }
          html += '</tbody></table>';
        }
      }
      if (r.output_dir) html += `<div style="margin-top:8px"><strong>输出目录：</strong><br>${r.output_dir}</div>`;
      if (r.suggestion) html += `<div style="margin-top:8px"><strong>建议：</strong> ${r.suggestion}</div>`;
      resultBox.innerHTML = html;
    }

    async function refresh() {
      if (!currentJob) return;
      const res = await fetch('/api/jobs/' + currentJob);
      const data = await res.json();
      jobStatusEl.textContent = data.status;
      logBox.textContent = data.log || '';
      renderResult(data);
      logBox.scrollTop = logBox.scrollHeight;
      if (data.status === 'complete' || data.status === 'failed') {
        clearInterval(timer);
        document.getElementById('submitBtn').disabled = false;
        document.getElementById('exampleBtn').disabled = false;
      }
    }

    document.getElementById('refreshBtn').addEventListener('click', refresh);
    document.getElementById('exampleBtn').addEventListener('click', async () => {
      document.getElementById('submitBtn').disabled = true;
      document.getElementById('exampleBtn').disabled = true;
      logBox.textContent = '正在提交 ShapeMapper2 官方示例任务...';
      const formData = new FormData();
      formData.append('example_path', document.getElementById('examplePath').value || '');
      formData.append('example_output_dir', document.getElementById('exampleOutputDir').value || '');
      const res = await fetch('/api/run-example', { method: 'POST', body: formData });
      const data = await res.json();
      if (!res.ok) {
        logBox.textContent = data.error || '提交示例任务失败';
        document.getElementById('submitBtn').disabled = false;
        document.getElementById('exampleBtn').disabled = false;
        return;
      }
      currentJob = data.job_id;
      jobIdEl.textContent = currentJob;
      jobStatusEl.textContent = 'queued';
      resultBox.innerHTML = '官方示例任务已提交，等待结果...';
      timer = setInterval(refresh, 1500);
      refresh();
    });

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const groups = collectSampleGroups();
      if (!groups.length && new FormData(form).get('run_mode') !== 'assemble') {
        alert('请至少填写一套样本组的 Modified 和 Untreated 识别序列。');
        return;
      }
      document.getElementById('submitBtn').disabled = true;
      logBox.textContent = '正在提交任务...';
      const res = await fetch('/api/run', { method: 'POST', body: new FormData(form) });
      const data = await res.json();
      if (!res.ok) {
        logBox.textContent = data.error || '提交失败';
        document.getElementById('submitBtn').disabled = false;
        return;
      }
      currentJob = data.job_id;
      jobIdEl.textContent = currentJob;
      jobStatusEl.textContent = 'queued';
      resultBox.innerHTML = '任务已提交，等待结果...';
      timer = setInterval(refresh, 1500);
      refresh();
    });
  </script>
</body>
</html>
"""


def safe_name(name):
    name = Path(name or "uploaded").name
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)


def split_seqs(text):
    return [x.upper().replace("U", "T") for x in re.split(r"[\s,;]+", text or "") if x.strip()]


def wsl_path(value):
    value = (value or "").strip().strip('"').strip("'")
    if not value:
        return ""
    if re.match(r"^[A-Za-z]:\\", value):
        out = subprocess.check_output(["wslpath", "-a", value], text=True).strip()
        return out
    path = Path(value).expanduser()
    if path.is_absolute():
        return str(path)
    return str((ROOT / path).resolve())


def parse_multipart(handler):
    ctype = handler.headers.get("Content-Type", "")
    length = int(handler.headers.get("Content-Length", "0"))
    body = handler.rfile.read(length)
    message = BytesParser(policy=default).parsebytes(
        b"Content-Type: " + ctype.encode() + b"\r\nMIME-Version: 1.0\r\n\r\n" + body
    )
    fields = {}
    files = {}
    for part in message.iter_parts():
        disp = part.get_content_disposition()
        if disp != "form-data":
            continue
        name = part.get_param("name", header="content-disposition")
        filename = part.get_filename()
        payload = part.get_payload(decode=True) or b""
        if filename:
            if filename and payload:
                files[name] = (safe_name(filename), payload)
        else:
            fields[name] = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
    return fields, files


def save_upload(files, key, upload_dir):
    item = files.get(key)
    if not item:
        return ""
    filename, payload = item
    path = upload_dir / filename
    path.write_bytes(payload)
    return str(path)


def demux_samples_from_fields(fields):
    samples = []
    raw_groups = (fields.get("sample_groups_json") or "").strip()
    if raw_groups:
        for group in json.loads(raw_groups):
            group_name = group.get("group_name") or group.get("name") or "default"
            for item in group.get("samples", []):
                role = (item.get("role") or "").lower()
                r1_primers = split_seqs(item.get("r1", ""))
                r2_primers = split_seqs(item.get("r2", ""))
                if not role or (not r1_primers and not r2_primers):
                    continue
                samples.append(
                    {
                        "group": group_name,
                        "name": (item.get("name") or role).strip() or role,
                        "role": role,
                        "r1_primers": r1_primers,
                        "r2_primers": r2_primers,
                    }
                )
        return samples

    for role in ["modified", "untreated", "denatured"]:
        r1_primers = split_seqs(fields.get(f"{role}_r1", ""))
        r2_primers = split_seqs(fields.get(f"{role}_r2", ""))
        if not r1_primers and not r2_primers:
            continue
        sample_name = (fields.get(f"{role}_name") or role).strip() or role
        samples.append(
            {
                "name": sample_name,
                "role": role,
                "r1_primers": r1_primers,
                "r2_primers": r2_primers,
            }
        )
    return samples


def build_config(fields, files, job_id):
    project_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", fields.get("project_name", "shape_map_project")).strip("_")
    if not project_name:
        project_name = f"shape_map_{job_id}"
    upload_dir = UPLOAD_ROOT / job_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    out_dir = Path(wsl_path(fields.get("output_dir"))) if fields.get("output_dir", "").strip() else RESULT_ROOT / project_name
    out_dir.mkdir(parents=True, exist_ok=True)

    r1 = save_upload(files, "r1_file", upload_dir) or wsl_path(fields.get("r1_path"))
    r2 = save_upload(files, "r2_file", upload_dir) or wsl_path(fields.get("r2_path"))

    config = {
        "project_name": project_name,
        "output_dir": str(out_dir),
        "input": {"r1": r1, "r2": r2},
        "demux": {
            "search_bases": int(fields.get("search_bases") or 40),
            "max_mismatches": int(fields.get("max_mismatches") or 1),
            "anchored": "anchored" in fields,
            "match_mode": "any",
            "check_reverse_complement": "check_reverse_complement" in fields,
            "samples": [],
        },
        "shapemapper": {
            "executable": "~/tools/shapemapper2-2.3/shapemapper",
            "amplicon": "amplicon" in fields,
            "nproc": int(fields.get("nproc") or 4),
            "min_depth": int(fields.get("min_depth") or 1000),
            "min_mapq": int(fields.get("min_mapq") or 10),
            "min_qual_to_trim": 20,
            "window_to_trim": 5,
            "min_qual_to_count": 30,
            "max_bg": float(fields.get("max_bg") or 0.05),
            "max_paired_fragment_length": 800,
        },
    }

    primers_file = save_upload(files, "primers_file", upload_dir)
    if primers_file:
        config["shapemapper"]["primers_file"] = primers_file

    config["demux"]["samples"] = demux_samples_from_fields(fields)

    ref_mode = fields.get("ref_mode", "target")
    if ref_mode == "assemble":
        fragments = save_upload(files, "fragments_file", upload_dir)
        order = [x.strip() for x in (fields.get("fragment_order") or "").splitlines() if x.strip()]
        config["reference_assembly"] = {
            "fragments_fasta": fragments,
            "output_fasta": str(out_dir / "assembled_target.fa"),
            "name": fields.get("assembled_name") or "full_target",
            "min_overlap": int(fields.get("min_overlap") or 20),
            "max_mismatches": 0,
            "allow_no_overlap": False,
        }
        if order:
            config["reference_assembly"]["order"] = order
    elif ref_mode == "existing":
        config["target"] = wsl_path(fields.get("target_path"))
    else:
        config["target"] = save_upload(files, "target_file", upload_dir)

    config_path = PROJECT_ROOT / f"{project_name}.{job_id}.json"
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    return config_path


def count_fastq_records(path):
    opener = gzip.open if str(path).endswith(".gz") else open
    line_count = 0
    with opener(path, "rt") as handle:
        for line_count, _line in enumerate(handle, start=1):
            pass
    return line_count // 4


def prepare_official_example(job_id, example_path, output_dir_value=""):
    example_src = Path(wsl_path(example_path)).expanduser() if example_path.strip() else Path.home() / "tools" / "shapemapper2-2.3" / "example_data"
    if not example_src.exists():
        raise FileNotFoundError(
            f"ShapeMapper2 example_data was not found: {example_src}. "
            "Install ShapeMapper2 or fill in the local example_data path."
        )

    project_name = f"official_tpp_example_{job_id}"
    output_dir = Path(wsl_path(output_dir_value)) if output_dir_value.strip() else RESULT_ROOT / project_name
    demux_dir = output_dir / "demux"
    output_dir.mkdir(parents=True, exist_ok=True)
    demux_dir.mkdir(parents=True, exist_ok=True)

    role_sources = {
        "modified": "TPPplus",
        "untreated": "TPPminus",
        "denatured": "TPPdenat",
    }
    role_counts = {}
    sample_counts = {}
    for role, folder_name in role_sources.items():
        source_folder = example_src / folder_name
        if not source_folder.exists():
            raise FileNotFoundError(f"Missing official example folder: {source_folder}")
        dest_folder = demux_dir / role
        if dest_folder.exists():
            shutil.rmtree(dest_folder)
        shutil.copytree(source_folder, dest_folder)
        count = sum(count_fastq_records(path) for path in dest_folder.glob("*R1*.fastq.gz"))
        role_counts[role] = count
        sample_counts[folder_name] = count

    target_src = example_src / "TPP.fa"
    if not target_src.exists():
        raise FileNotFoundError(f"Missing official example target FASTA: {target_src}")
    target_dest = output_dir / "TPP.fa"
    shutil.copy2(target_src, target_dest)

    demux_summary = {
        "total": sum(role_counts.values()),
        "unmatched": 0,
        "ambiguous": 0,
        "samples": sample_counts,
        "roles": role_counts,
    }
    (demux_dir / "demux_summary.json").write_text(json.dumps(demux_summary, indent=2), encoding="utf-8")

    config = {
        "project_name": project_name,
        "target": str(target_dest),
        "output_dir": str(output_dir),
        "input": {},
        "demux": {"samples": []},
        "shapemapper": {
            "executable": "~/tools/shapemapper2-2.3/shapemapper",
            "amplicon": True,
            "nproc": 4,
            "min_depth": 1000,
            "min_mapq": 10,
            "min_qual_to_trim": 20,
            "window_to_trim": 5,
            "min_qual_to_count": 30,
            "max_bg": 0.05,
            "max_paired_fragment_length": 800,
        },
    }
    config_path = PROJECT_ROOT / f"{project_name}.json"
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    return config_path


def run_job(job_id, config_path, mode):
    job = JOBS[job_id]
    log_path = job["log_path"]
    args = ["python3", str(PIPELINE), str(config_path)]
    if mode == "demux":
        args.append("--demux-only")
    elif mode == "assemble":
        args.append("--assemble-only")
    elif mode == "skip_demux":
        args.append("--skip-demux")
    job["status"] = "running"
    with log_path.open("w", encoding="utf-8", errors="replace") as log:
        log.write("Command: " + " ".join(shlex.quote(x) for x in args) + "\n\n")
        log.flush()
        proc = subprocess.Popen(args, cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT, text=True)
        rc = proc.wait()
        log.write(f"\nExit code: {rc}\n")
    job["status"] = "complete" if rc == 0 else "failed"


def load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return None


def make_result(job, log):
    config = load_json(job["config_path"]) or {}
    output_dir = Path(config.get("output_dir", "")) if config.get("output_dir") else None
    run_summary = load_json(output_dir / "run_summary.json") if output_dir else None
    demux_summary = load_json(output_dir / "demux" / "demux_summary.json") if output_dir else None

    result = {
        "level": "ok" if job["status"] == "complete" else "warn",
        "title": "任务完成" if job["status"] == "complete" else "任务未完成",
        "message": "",
        "output_dir": str(output_dir) if output_dir else "",
        "demux": demux_summary,
        "suggestion": "",
    }

    if run_summary:
        result["message"] = run_summary.get("message", "")
        if run_summary.get("shapemapper_out"):
            result["shapemapper_out"] = run_summary["shapemapper_out"]

    if demux_summary:
        roles = demux_summary.get("roles", {})
        total = int(demux_summary.get("total", 0))
        matched = sum(int(roles.get(role, 0)) for role in ["modified", "untreated", "denatured"])
        if total and matched / total < 0.05:
            result["level"] = "warn"
            result["title"] = "样本拆分命中率很低"
            result["message"] = f"只匹配到 {matched} / {total} 条 reads。"
            result["suggestion"] = "优先检查 barcode 是否在 R1/R2 开头、方向是否正确、是否应该只运行拆分模式。"
        if int(roles.get("modified", 0)) == 0 or int(roles.get("untreated", 0)) == 0:
            result["level"] = "warn"
            result["title"] = "关键分组为空"
            result["message"] = "modified 或 untreated 没有 reads，ShapeMapper2 无法进行标准 SHAPE-MaP 分析。"
            result["suggestion"] = "先用只拆分样本模式调 barcode；必要时扫描 R1/R2 开头序列。"
        elif int(roles.get("denatured", 0)) == 0:
            result["level"] = "warn"
            result["title"] = "denatured 分组为空"
            result["message"] = "可以做两样本分析，但不适合标准三样本归一化。"
            result["suggestion"] = "确认 denatured barcode 或选择不包含 denatured 的分析配置。"

    if "Operation not supported" in log and "os.mkfifo" in log:
        result["level"] = "warn"
        result["title"] = "ShapeMapper2 临时目录不兼容"
        result["message"] = "ShapeMapper2 在 Windows 挂载目录创建 Linux 管道失败。"
        result["suggestion"] = "程序已更新为使用 WSL 原生临时目录；请重新提交任务。"
    elif "No such file or directory" in log:
        result["level"] = "warn"
        result["title"] = "找不到输入文件"
        result["message"] = "某个 FASTQ/FASTA 路径不存在。"
        result["suggestion"] = "检查路径是否带引号，或把文件放到 data/raw 后使用相对路径。"
    elif "Demultiplexing did not produce enough reads" in log:
        result["level"] = "warn"
        result["title"] = "拆分结果不足以运行 ShapeMapper2"
        result["message"] = "至少 modified 和 untreated 需要有非零 reads。"
        result["suggestion"] = "先运行只拆分样本模式，确认 barcode 设置。"

    return result


class Handler(BaseHTTPRequestHandler):
    def json_response(self, payload, status=200):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            data = INDEX_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if parsed.path.startswith("/api/jobs/"):
            job_id = parsed.path.rsplit("/", 1)[-1]
            job = JOBS.get(job_id)
            if not job:
                self.json_response({"error": "job not found"}, 404)
                return
            log = ""
            if job["log_path"].exists():
                log = job["log_path"].read_text(encoding="utf-8", errors="replace")[-30000:]
            self.json_response({"job_id": job_id, "status": job["status"], "log": log, "result": make_result(job, log)})
            return
        self.send_error(404)

    def do_POST(self):
        if self.path == "/api/run-example":
            try:
                fields, _files = parse_multipart(self)
                job_id = time.strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8]
                config_path = prepare_official_example(
                    job_id,
                    fields.get("example_path", ""),
                    fields.get("example_output_dir", ""),
                )
                log_path = RESULT_ROOT / "web_logs" / f"{job_id}.log"
                log_path.parent.mkdir(parents=True, exist_ok=True)
                JOBS[job_id] = {"status": "queued", "config_path": config_path, "log_path": log_path}
                threading.Thread(target=run_job, args=(job_id, config_path, "skip_demux"), daemon=True).start()
                self.json_response({"job_id": job_id, "config": str(config_path)})
            except Exception as exc:
                self.json_response({"error": str(exc)}, 400)
            return
        if self.path != "/api/run":
            self.send_error(404)
            return
        try:
            fields, files = parse_multipart(self)
            job_id = time.strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8]
            config_path = build_config(fields, files, job_id)
            log_path = RESULT_ROOT / "web_logs" / f"{job_id}.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            JOBS[job_id] = {"status": "queued", "config_path": config_path, "log_path": log_path}
            mode = fields.get("run_mode", "full")
            threading.Thread(target=run_job, args=(job_id, config_path, mode), daemon=True).start()
            self.json_response({"job_id": job_id, "config": str(config_path)})
        except Exception as exc:
            self.json_response({"error": str(exc)}, 400)

    def log_message(self, fmt, *args):
        print(f"[web] {self.address_string()} - {fmt % args}", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Local web UI for SHAPE-MaP analysis.")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    PROJECT_ROOT.mkdir(parents=True, exist_ok=True)
    RESULT_ROOT.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"SHAPE-MaP Local Runner is running at http://127.0.0.1:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
