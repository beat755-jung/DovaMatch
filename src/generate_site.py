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
  .bio {{ margin-top: 6px; line-height: 1.7; white-space: pre-wrap; }}
  .bio-label {{
    margin-top: 20px; font-size: 12px; font-weight: 700; color: #888;
    text-transform: uppercase; letter-spacing: 0.04em;
  }}
  .events {{ margin-top: 24px; }}
  .event {{ margin-bottom: 12px; padding: 10px 14px; background: #f4f4f8; border-radius: 6px; }}
  a {{ color: #3b53d8; }}
  .placeholder {{ color: #888; }}
  #list .section-label {{
    padding: 10px 16px 4px; font-size: 12px; font-weight: 700; color: #888;
    text-transform: uppercase; letter-spacing: 0.04em;
  }}
  .analysis {{ margin-top: 24px; }}
  .analysis h2 {{ font-size: 16px; border-bottom: 1px solid #eee; padding-bottom: 6px; }}
  .analysis .philosophy {{ font-style: italic; line-height: 1.7; color: #333; }}
  .keyword-tags {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }}
  .keyword-tag {{
    background: #eef1ff; color: #3b53d8; border-radius: 999px;
    padding: 4px 12px; font-size: 13px;
  }}
  .exhibition-list {{ margin: 6px 0 0; padding-left: 18px; line-height: 1.7; }}
  .review-note {{ color: #888; font-size: 12px; margin-top: 4px; }}
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
  .stage-list {{ margin-top: 10px; display: flex; flex-direction: column; gap: 10px; }}
  .stage-card {{ background: #f4f4f8; border-left: 4px solid #3b53d8; border-radius: 6px; padding: 12px 16px; }}
  .stage-card .range {{ font-weight: 700; margin-bottom: 4px; }}
  .code-block {{
    background: #2b2b2b; color: #eee; font-family: Consolas, monospace; font-size: 13px;
    padding: 10px 14px; border-radius: 6px; margin: 6px 0; white-space: pre-wrap;
  }}
  .pitfall-list {{ margin: 6px 0 0; padding-left: 18px; line-height: 1.8; }}
  .summary-box {{
    background: #eef1ff; border-radius: 8px; padding: 16px 20px; margin-top: 12px;
    line-height: 1.7; font-weight: 500;
  }}
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
<script id="alumni-data" type="application/json">{alumni_json}</script>
<script id="admission-data" type="application/json">{admission_json}</script>
<script>
  const faculty = JSON.parse(document.getElementById('faculty-data').textContent);
  const alumni = JSON.parse(document.getElementById('alumni-data').textContent);
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

  const facultyLabel = document.createElement('div');
  facultyLabel.className = 'section-label';
  facultyLabel.textContent = '교수진 (Faculty)';
  listEl.appendChild(facultyLabel);

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

  if (alumni.length > 0) {{
    const alumniLabel = document.createElement('div');
    alumniLabel.className = 'section-label';
    alumniLabel.textContent = '한국인 DoVA 동문 (Alumni)';
    listEl.appendChild(alumniLabel);

    alumni.forEach((person) => {{
      const btn = document.createElement('button');
      btn.textContent = person.name;
      btn.addEventListener('click', () => {{
        document.querySelectorAll('#list button').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        showDetail(person);
      }});
      listEl.appendChild(btn);
    }});
  }}

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
    if (person.url) {{
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

    const bioLabel = document.createElement('div');
    bioLabel.className = 'bio-label';
    bioLabel.textContent = 'Bio (English)';
    textCol.appendChild(bioLabel);

    const bio = document.createElement('div');
    bio.className = 'bio';
    bio.textContent = person.bio;
    textCol.appendChild(bio);

    if (person.bio_ko) {{
      const bioKoLabel = document.createElement('div');
      bioKoLabel.className = 'bio-label';
      bioKoLabel.textContent = '소개 (한국어)';
      textCol.appendChild(bioKoLabel);

      const bioKo = document.createElement('div');
      bioKo.className = 'bio';
      bioKo.textContent = person.bio_ko;
      textCol.appendChild(bioKo);
    }}

    if (person.current_activity_ko) {{
      const actWrap = document.createElement('div');
      actWrap.className = 'analysis';
      const h2 = document.createElement('h2');
      h2.textContent = '현재 활동';
      actWrap.appendChild(h2);
      const p = document.createElement('p');
      p.textContent = person.current_activity_ko;
      actWrap.appendChild(p);
      textCol.appendChild(actWrap);
    }}

    if (person.philosophy || person.academic_orientation_ko ||
        (person.visual_languages && person.visual_languages.length > 0)) {{
      const analysisWrap = document.createElement('div');
      analysisWrap.className = 'analysis';

      if (person.philosophy) {{
        const h2 = document.createElement('h2');
        h2.textContent = '예술 철학';
        analysisWrap.appendChild(h2);
        const p = document.createElement('p');
        p.className = 'philosophy';
        p.textContent = person.philosophy;
        analysisWrap.appendChild(p);
      }}

      if (person.academic_orientation_ko) {{
        const h2 = document.createElement('h2');
        h2.textContent = '학문적 성향';
        analysisWrap.appendChild(h2);
        const p = document.createElement('p');
        p.textContent = person.academic_orientation_ko;
        analysisWrap.appendChild(p);
      }}

      if (person.visual_languages && person.visual_languages.length > 0) {{
        const h2 = document.createElement('h2');
        h2.textContent = '표현 언어 (Visual Languages)';
        analysisWrap.appendChild(h2);
        const tags = document.createElement('div');
        tags.className = 'keyword-tags';
        person.visual_languages.forEach(kw => {{
          const tag = document.createElement('span');
          tag.className = 'keyword-tag';
          tag.textContent = kw;
          tags.appendChild(tag);
        }});
        analysisWrap.appendChild(tags);
      }}

      if (person.key_exhibitions && person.key_exhibitions.length > 0) {{
        const h2 = document.createElement('h2');
        h2.textContent = '대표 전시 및 성과';
        analysisWrap.appendChild(h2);
        const ul = document.createElement('ul');
        ul.className = 'exhibition-list';
        person.key_exhibitions.forEach(item => {{
          const li = document.createElement('li');
          li.textContent = item;
          ul.appendChild(li);
        }});
        analysisWrap.appendChild(ul);
      }}

      const note = document.createElement('div');
      note.className = 'review-note';
      note.textContent = '※ 위 철학/표현 언어/전시 항목은 자동 추출된 참고 자료이며, 실제 인용 전 원문 확인을 권장합니다.';
      analysisWrap.appendChild(note);

      textCol.appendChild(analysisWrap);
    }}

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

    // faculty academic orientation
    if (info.faculty_academic_orientation) {{
      const fao = info.faculty_academic_orientation;
      const faoSection = addSection(page, 'DoVA 교수진의 학문적 성향');

      const intro = document.createElement('p');
      intro.textContent = fao.intro;
      faoSection.appendChild(intro);

      if (fao.themes) {{
        const themeList = document.createElement('div');
        themeList.className = 'stage-list';
        fao.themes.forEach(theme => {{
          const card = document.createElement('div');
          card.className = 'stage-card';
          const title = document.createElement('div');
          title.className = 'range';
          title.textContent = theme.title;
          card.appendChild(title);
          const desc = document.createElement('div');
          desc.textContent = theme.description;
          card.appendChild(desc);
          if (theme.examples && theme.examples.length > 0) {{
            const ul = document.createElement('ul');
            ul.className = 'exhibition-list';
            theme.examples.forEach(ex => {{
              const li = document.createElement('li');
              li.textContent = ex;
              ul.appendChild(li);
            }});
            card.appendChild(ul);
          }}
          themeList.appendChild(card);
        }});
        faoSection.appendChild(themeList);
      }}

      if (fao.summary) {{
        const summaryBox = document.createElement('div');
        summaryBox.className = 'summary-box';
        summaryBox.textContent = fao.summary;
        faoSection.appendChild(summaryBox);
      }}

      if (fao.application_tip) {{
        const tipLabel = document.createElement('div');
        tipLabel.className = 'tip';
        tipLabel.textContent = '지원 전략 적용 팁:';
        faoSection.appendChild(tipLabel);
        const tipP = document.createElement('p');
        tipP.textContent = fao.application_tip;
        faoSection.appendChild(tipP);
      }}
    }}

    // portfolio strategy
    if (info.portfolio_strategy) {{
      const ps = info.portfolio_strategy;
      const psSection = addSection(page, '포트폴리오(20점) 구성 전략');

      const intro = document.createElement('p');
      intro.textContent = ps.intro;
      psSection.appendChild(intro);

      if (ps.sequencing_stages) {{
        const h3 = document.createElement('h3');
        h3.textContent = '시퀀싱 전략: 기승전결이 있는 시각 논문 만들기';
        psSection.appendChild(h3);
        const stageList = document.createElement('div');
        stageList.className = 'stage-list';
        ps.sequencing_stages.forEach(stage => {{
          const card = document.createElement('div');
          card.className = 'stage-card';
          const range = document.createElement('div');
          range.className = 'range';
          range.textContent = stage.range;
          const desc = document.createElement('div');
          desc.textContent = stage.description;
          card.appendChild(range);
          card.appendChild(desc);
          stageList.appendChild(card);
        }});
        psSection.appendChild(stageList);
      }}

      if (ps.slideroom_text_tips) {{
        const tips = ps.slideroom_text_tips;
        const h3 = document.createElement('h3');
        h3.textContent = 'Slideroom 텍스트 입력란 활용하기';
        psSection.appendChild(h3);
        const tipsIntro = document.createElement('p');
        tipsIntro.textContent = tips.intro;
        psSection.appendChild(tipsIntro);

        const badLabel = document.createElement('div');
        badLabel.className = 'tip';
        badLabel.textContent = '흔한 실수:';
        psSection.appendChild(badLabel);
        const badBlock = document.createElement('div');
        badBlock.className = 'code-block';
        badBlock.textContent = tips.common_mistake;
        psSection.appendChild(badBlock);

        const goodLabel = document.createElement('div');
        goodLabel.className = 'tip';
        goodLabel.textContent = '합격 전략 (재료 란 활용):';
        psSection.appendChild(goodLabel);
        const goodBlock = document.createElement('div');
        goodBlock.className = 'code-block';
        goodBlock.textContent = tips.better_practice;
        psSection.appendChild(goodBlock);

        const descTip = document.createElement('p');
        descTip.className = 'tip';
        descTip.textContent = 'Description(설명)란 활용: ' + tips.description_field_tip;
        psSection.appendChild(descTip);
      }}

      if (ps.pitfalls) {{
        const h3 = document.createElement('h3');
        h3.textContent = '절대 넣지 말아야 할 것';
        psSection.appendChild(h3);
        const ul = document.createElement('ul');
        ul.className = 'pitfall-list';
        ps.pitfalls.forEach(item => {{
          const li = document.createElement('li');
          li.textContent = item;
          ul.appendChild(li);
        }});
        psSection.appendChild(ul);
      }}

      if (ps.summary) {{
        const summaryBox = document.createElement('div');
        summaryBox.className = 'summary-box';
        summaryBox.textContent = ps.summary;
        psSection.appendChild(summaryBox);
      }}
    }}

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


def generate_html(faculty_data, admission_info, alumni_data=None):
    return PAGE_TEMPLATE.format(
        faculty_json=_safe_json(faculty_data),
        alumni_json=_safe_json(alumni_data or []),
        admission_json=_safe_json(admission_info),
    )


def main():
    with open(DATA_DIR / "faculty_data.json", "r", encoding="utf-8") as f:
        faculty_data = json.load(f)
    with open(DATA_DIR / "admission_info.json", "r", encoding="utf-8") as f:
        admission_info = json.load(f)

    alumni_path = DATA_DIR / "alumni_data.json"
    alumni_data = []
    if alumni_path.exists():
        with open(alumni_path, "r", encoding="utf-8") as f:
            alumni_data = json.load(f)

    SITE_DIR.mkdir(exist_ok=True)
    output_path = SITE_DIR / "index.html"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(generate_html(faculty_data, admission_info, alumni_data))

    print(
        f"Saved site with {len(faculty_data)} faculty and {len(alumni_data)} alumni "
        f"profiles to {output_path}"
    )
    return output_path


if __name__ == "__main__":
    main()
