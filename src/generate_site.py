"""Builds a self-contained static HTML viewer from data/faculty_data.json.

Clicking a professor's name in the left list shows their full profile
(title, contact info, bio, homepage, related events) on the right.
"""

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SITE_DIR = Path(__file__).resolve().parent.parent / "site"

PAGE_TEMPLATE = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>DovaMatch - DoVA Faculty</title>
<style>
  body {{ margin: 0; font-family: -apple-system, Segoe UI, sans-serif; display: flex; height: 100vh; }}
  #list {{ width: 280px; overflow-y: auto; border-right: 1px solid #ddd; background: #fafafa; }}
  #list button {{
    display: block; width: 100%; text-align: left; padding: 12px 16px;
    border: none; border-bottom: 1px solid #eee; background: none; cursor: pointer; font-size: 14px;
  }}
  #list button:hover, #list button.active {{ background: #e8ecff; }}
  #list button.info-btn {{ font-weight: 600; background: #eef1ff; }}
  #list .divider {{ border-bottom: 2px solid #ccc; }}
  #detail {{ flex: 1; overflow-y: auto; padding: 32px 40px; }}
  .detail-grid {{ display: flex; gap: 40px; align-items: flex-start; }}
  .detail-text {{ flex: 1 1 50%; min-width: 0; }}
  .detail-image {{ flex: 1 1 50%; min-width: 0; position: sticky; top: 32px; }}
  .detail-image img {{ width: 100%; height: auto; border-radius: 8px; display: block; }}
  .detail-text h1 {{ margin-top: 0; }}
  .meta {{ color: #555; margin-bottom: 4px; }}
  .bio {{ margin-top: 20px; line-height: 1.7; white-space: pre-wrap; }}
  .events {{ margin-top: 24px; }}
  .event {{ margin-bottom: 12px; padding: 10px 14px; background: #f4f4f8; border-radius: 6px; }}
  a {{ color: #3b53d8; }}
  .placeholder {{ color: #888; }}
  .info-page section {{ margin-bottom: 32px; max-width: 900px; }}
  .info-page h2 {{ border-bottom: 2px solid #eee; padding-bottom: 6px; }}
  .info-page table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
  .info-page th, .info-page td {{ text-align: left; padding: 10px 12px; border: 1px solid #e0e0e0; vertical-align: top; white-space: pre-line; }}
  .info-page th {{ background: #f4f4f8; }}
  .info-page .tip {{ color: #666; font-size: 13px; }}
  .score-cards {{ display: flex; gap: 12px; flex-wrap: wrap; margin-top: 10px; }}
  .score-card {{ background: #f4f4f8; border-radius: 8px; padding: 12px 18px; min-width: 100px; }}
  .score-card .label {{ font-size: 12px; color: #666; }}
  .score-card .value {{ font-size: 20px; font-weight: 700; }}
  @media (max-width: 800px) {{
    .detail-grid {{ flex-direction: column; }}
    .detail-image {{ position: static; }}
  }}
</style>
</head>
<body>
<div id="list"></div>
<div id="detail"><p class="placeholder">왼쪽에서 교수를 선택하세요.</p></div>
<script id="faculty-data" type="application/json">{faculty_json}</script>
<script id="admission-data" type="application/json">{admission_json}</script>
<script>
  const faculty = JSON.parse(document.getElementById('faculty-data').textContent);
  const admissionInfo = JSON.parse(document.getElementById('admission-data').textContent);
  const listEl = document.getElementById('list');
  const detailEl = document.getElementById('detail');

  const infoBtn = document.createElement('button');
  infoBtn.textContent = '📋 DoVA 지원 요건 & 내 점수';
  infoBtn.className = 'info-btn divider';
  infoBtn.addEventListener('click', () => {{
    document.querySelectorAll('#list button').forEach(b => b.classList.remove('active'));
    infoBtn.classList.add('active');
    showInfoPage(admissionInfo);
  }});
  listEl.appendChild(infoBtn);

  faculty.forEach((person, idx) => {{
    const btn = document.createElement('button');
    btn.textContent = person.name;
    btn.addEventListener('click', () => {{
      document.querySelectorAll('#list button').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      showDetail(person);
    }});
    listEl.appendChild(btn);
  }});

  function showDetail(person) {{
    detailEl.innerHTML = '';

    const grid = document.createElement('div');
    grid.className = 'detail-grid';

    const textCol = document.createElement('div');
    textCol.className = 'detail-text';

    const h1 = document.createElement('h1');
    h1.textContent = person.name;
    textCol.appendChild(h1);

    if (person.title) {{
      const p = document.createElement('div');
      p.className = 'meta';
      p.textContent = person.title;
      textCol.appendChild(p);
    }}
    if (person.office) {{
      const p = document.createElement('div');
      p.className = 'meta';
      p.textContent = person.office;
      textCol.appendChild(p);
    }}
    if (person.teaching_since) {{
      const p = document.createElement('div');
      p.className = 'meta';
      p.textContent = person.teaching_since;
      textCol.appendChild(p);
    }}
    if (person.email) {{
      const p = document.createElement('div');
      p.className = 'meta';
      const a = document.createElement('a');
      a.href = 'mailto:' + person.email;
      a.textContent = person.email;
      p.appendChild(a);
      textCol.appendChild(p);
    }}
    if (person.homepage) {{
      const p = document.createElement('div');
      p.className = 'meta';
      const a = document.createElement('a');
      a.href = person.homepage;
      a.target = '_blank';
      a.rel = 'noopener';
      a.textContent = person.homepage;
      p.appendChild(a);
      textCol.appendChild(p);
    }}
    {{
      const p = document.createElement('div');
      p.className = 'meta';
      const a = document.createElement('a');
      a.href = person.url;
      a.target = '_blank';
      a.rel = 'noopener';
      a.textContent = 'DoVA 프로필 페이지 원문';
      p.appendChild(a);
      textCol.appendChild(p);
    }}

    const bio = document.createElement('div');
    bio.className = 'bio';
    bio.textContent = person.bio;
    textCol.appendChild(bio);

    if (person.events && person.events.length > 0) {{
      const eventsWrap = document.createElement('div');
      eventsWrap.className = 'events';
      const h2 = document.createElement('h2');
      h2.textContent = 'Related Events';
      eventsWrap.appendChild(h2);
      person.events.forEach(ev => {{
        const evEl = document.createElement('div');
        evEl.className = 'event';
        const title = document.createElement('a');
        title.href = ev.url;
        title.target = '_blank';
        title.rel = 'noopener';
        title.textContent = ev.title;
        evEl.appendChild(title);
        const info = document.createElement('div');
        info.textContent = [ev.date, ev.host, ev.location].filter(Boolean).join(' · ');
        evEl.appendChild(info);
        eventsWrap.appendChild(evEl);
      }});
      textCol.appendChild(eventsWrap);
    }}

    grid.appendChild(textCol);

    if (person.image) {{
      const imageCol = document.createElement('div');
      imageCol.className = 'detail-image';
      const img = document.createElement('img');
      img.src = person.image;
      img.alt = person.name;
      imageCol.appendChild(img);
      grid.appendChild(imageCol);
    }}

    detailEl.appendChild(grid);
  }}

  function addSection(container, titleText) {{
    const section = document.createElement('section');
    const h2 = document.createElement('h2');
    h2.textContent = titleText;
    section.appendChild(h2);
    container.appendChild(section);
    return section;
  }}

  function showInfoPage(info) {{
    detailEl.innerHTML = '';

    const page = document.createElement('div');
    page.className = 'info-page';

    const h1 = document.createElement('h1');
    h1.textContent = 'DoVA 지원 요건 & 내 점수';
    page.appendChild(h1);

    // my scores
    const scoreSection = addSection(page, '내 어학 점수 (TOEFL)');
    const cards = document.createElement('div');
    cards.className = 'score-cards';
    const scoreEntries = [
      ['총점 (뉴토플)', info.my_scores.toefl_new_total],
      ['총점 (구토플 환산)', info.my_scores.toefl_old_total],
      ['Reading', info.my_scores.reading],
      ['Listening', info.my_scores.listening],
      ['Speaking', info.my_scores.speaking],
      ['Writing', info.my_scores.writing],
    ];
    scoreEntries.forEach(([label, value]) => {{
      const card = document.createElement('div');
      card.className = 'score-card';
      const l = document.createElement('div');
      l.className = 'label';
      l.textContent = label;
      const v = document.createElement('div');
      v.className = 'value';
      v.textContent = value;
      card.appendChild(l);
      card.appendChild(v);
      cards.appendChild(card);
    }});
    scoreSection.appendChild(cards);

    // required documents
    const docsSection = addSection(page, '제출 서류 요건');
    const docsTable = document.createElement('table');
    docsTable.innerHTML = '<tr><th>구분</th><th>제출 요건 및 상세 내용</th><th>준비 팁</th></tr>';
    info.required_documents.forEach(doc => {{
      const tr = document.createElement('tr');
      const c1 = document.createElement('td');
      c1.textContent = doc.item;
      const c2 = document.createElement('td');
      c2.textContent = doc.requirement;
      const c3 = document.createElement('td');
      c3.className = 'tip';
      c3.textContent = doc.tip;
      tr.appendChild(c1);
      tr.appendChild(c2);
      tr.appendChild(c3);
      docsTable.appendChild(tr);
    }});
    docsSection.appendChild(docsTable);

    // TA eligibility
    const taSection = addSection(page, '대학원 조교(TA) 영어 자격 요건');
    const taDesc = document.createElement('p');
    taDesc.textContent = info.ta_eligibility.description;
    taSection.appendChild(taDesc);
    const taTable = document.createElement('table');
    taTable.innerHTML = '<tr><th>시험 구분</th><th>무심사 패스 기준</th><th>⚠️ 자체 추가 시험(AEPA) 필요 기준</th></tr>';
    info.ta_eligibility.table.forEach(row => {{
      const tr = document.createElement('tr');
      const c1 = document.createElement('td');
      c1.textContent = row.test;
      const c2 = document.createElement('td');
      c2.textContent = row.pass;
      const c3 = document.createElement('td');
      c3.textContent = row.review;
      tr.appendChild(c1);
      tr.appendChild(c2);
      tr.appendChild(c3);
      taTable.appendChild(tr);
    }});
    taSection.appendChild(taTable);
    const taNote = document.createElement('p');
    taNote.className = 'tip';
    taNote.textContent = '내 TOEFL Speaking 점수: ' + info.my_scores.speaking + ' → 26점 이상(뉴토플 5.5) 기준을 충족하여 별도 추가 시험 없이 조교 임용이 가능합니다.';
    taSection.appendChild(taNote);

    // score sending
    const sendSection = addSection(page, '영어 성적 송부처 (Where to Send)');
    const sendList = document.createElement('ul');
    const sendItems = [
      'TOEFL 기관 코드: ' + info.score_sending.toefl_code,
      'IELTS: ' + info.score_sending.ielts_note,
      'Account Name: ' + info.score_sending.ielts_account_name,
      'Address: ' + info.score_sending.ielts_address,
    ];
    sendItems.forEach(text => {{
      const li = document.createElement('li');
      li.textContent = text;
      sendList.appendChild(li);
    }});
    sendSection.appendChild(sendList);

    // contacts
    const contactSection = addSection(page, '문의처 및 연락처 안내');
    const contactList = document.createElement('ul');
    info.contacts.forEach(c => {{
      const li = document.createElement('li');
      const a = document.createElement('a');
      a.href = 'mailto:' + c.email;
      a.textContent = c.email;
      li.textContent = c.purpose + ': ';
      li.appendChild(a);
      contactList.appendChild(li);
    }});
    contactSection.appendChild(contactList);

    page.appendChild(contactSection);
    detailEl.appendChild(page);
  }}

  if (faculty.length > 0) {{
    listEl.querySelector('button:not(.info-btn)').click();
  }}
</script>
</body>
</html>
"""


def _safe_json(data):
    # guard against "</script>" appearing inside scraped text and closing the tag early
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def generate_html(faculty_data, admission_info):
    return PAGE_TEMPLATE.format(
        faculty_json=_safe_json(faculty_data),
        admission_json=_safe_json(admission_info),
    )


def main():
    with open(DATA_DIR / "faculty_data.json", "r", encoding="utf-8") as f:
        faculty_data = json.load(f)
    with open(DATA_DIR / "admission_info.json", "r", encoding="utf-8") as f:
        admission_info = json.load(f)

    SITE_DIR.mkdir(exist_ok=True)
    output_path = SITE_DIR / "index.html"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(generate_html(faculty_data, admission_info))

    print(f"Saved site with {len(faculty_data)} profiles to {output_path}")
    return output_path


if __name__ == "__main__":
    main()
