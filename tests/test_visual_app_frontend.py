from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


HTML=Path(__file__).parents[1]/"carrot_sim"/"visual_app.html"


def read_html():
  return HTML.read_text(encoding="utf-8")


def script_text():
  match=re.search(r"<script>(.*)</script>",read_html(),re.S)
  assert match
  return match.group(1)


def test_visual_shell_has_required_controls_and_authority_labels():
  html=read_html()
  for token in ("roadCanvas","playButton","restartButton","timeline",
                "playbackRate","runSelect","candidateSelect","eventTimeline",
                "recommendationStatus","realVehicleWriteStatus"):
    assert f'id="{token}"' in html
  assert "실차 쓰기" in html and "Coverage 부족" in html


def test_frontend_uses_one_frame_index_for_scene_cards_and_chart():
  js=script_text()
  assert "function seekFrame(index)" in js
  assert "renderFrame(state.frames[state.frameIndex])" in js
  assert "drawRoad(frame)" in js
  assert "updateMetrics(frame)" in js
  assert "updateChartCursor(frame)" in js


def test_missing_geometry_has_unavailable_renderer():
  js=script_text()
  assert "function renderUnavailable(field)" in js
  assert "poseUnavailable" in js
  assert "leadUnavailable" in js


def test_frame_loading_is_paged_and_bounded():
  js=script_text()
  assert "limit=500" in js
  assert "next_offset" in js
  assert "2000" not in js


def test_responsive_layout_and_local_only_copy():
  html=read_html()
  assert "@media (max-width: 900px)" in html
  assert "오프라인 로컬 시뮬레이터" in html
  assert "인터넷 연결 없이" in html


def test_candidate_overlay_has_fixed_colors_and_exact_grid_guard():
  html=read_html();js=script_text()
  assert "#8798a5" in html and "#ff9d3f" in html
  assert "function compatibleTimeGrid" in js
  assert "candidateSelect" in js and "loadCandidate" in js
  assert "TIME_GRID_MISMATCH" in js
  assert "CURRENT_REFERENCE_RETAINED_NO_CHANGE_PROMOTED" in html


def test_candidate_overlay_pages_with_baseline_and_missing_speed_is_not_zero():
  html=read_html();js=script_text()
  assert "candidateNextOffset" in js
  assert "candidatePage" in js
  assert "m.speed_mps==null?null:m.speed_mps*3.6" in js


def test_event_text_is_not_injected_as_html_and_late_candidate_catches_up():
  js=script_text()
  assert ".innerHTML=" not in js
  assert "document.createElement('li')" in js
  assert "while(state.candidateNextOffset!==null&&state.candidateFrames.length<state.frames.length)" in js


def test_optimization_campaign_status_is_visible_and_loaded_fail_closed():
  html=read_html();js=script_text()
  assert 'id="optimizationPhase"' in html
  assert 'id="optimizationRecommendation"' in html
  assert "/api/optimization/status" in js
  assert "/api/optimization/report" in js
  assert "실차 적용 권한 없음" in html


def run_frontend_expression(expression: str):
  elements = """new Proxy({}, {get:(items,id)=>items[id]??=( {
    textContent:'',className:'',value:'',style:{},firstElementChild:{},
    classList:{add(){}},addEventListener(){},replaceChildren(){},
    appendChild(){},width:960,height:520,getContext(){return canvasContext}
  })})"""
  source = script_text() + "\n;globalThis.__result=(" + expression + ");"
  harness = f"""
const vm=require('node:vm');
const gradient={{addColorStop(){{}}}};
const canvasContext=new Proxy(
  {{createLinearGradient:()=>gradient}},
  {{get:(target,key)=>target[key]??(()=>{{}}),set:(target,key,value)=>{{target[key]=value;return true}}}}
);
const elements={elements};
const context={{
  document:{{
    getElementById:(id)=>elements[id],
    createElement:()=>({{textContent:'',value:'',appendChild(){{}}}})
  }},
  window:{{addEventListener(){{}}}},
  fetch:async()=>({{ok:false,json:async()=>({{runs:[]}})}}),
  setInterval:()=>1,
  clearInterval(){{}},
  console
}};
vm.createContext(context);
vm.runInContext({json.dumps(source)},context);
process.stdout.write(JSON.stringify(context.__result));
"""
  completed = subprocess.run(
    ["node", "-e", harness], check=True, capture_output=True, text=True)
  return json.loads(completed.stdout)


def test_twin_scene_model_uses_only_data_backed_objects():
  expression = """twinSceneModel(
    {ego:{pose:{x_m:1,y_m:0.2,heading_rad:0.1}},
     lead:{id:'lead-1',distance_m:28.4,relative_speed_mps:-1.8},
     lanes:null},
    {ego:{pose:{x_m:1,y_m:0.5,heading_rad:0.15}}}
  )"""
  assert run_frontend_expression(expression) == {
    "poseAvailable": True,
    "lanesAvailable": False,
    "candidateAvailable": True,
    "candidateOffsetPx": 2,
    "leadOffsetPx": 85.2,
    "actors": [{
      "kind": "lead",
      "id": "lead-1",
      "distanceM": 28.4,
      "relativeSpeedMps": -1.8,
    }],
  }


def test_twin_renderer_updates_relation_panel_without_fake_traffic():
  expression = """(()=>{
    state.candidateFrames=[{ego:{pose:{x_m:1,y_m:0.5,heading_rad:0.15}}}];
    state.frameIndex=0;
    drawRoad({
      ego:{pose:{x_m:1,y_m:0.2,heading_rad:0.1}},
      lead:{id:'lead-1',distance_m:28.4,relative_speed_mps:-1.8},
      lanes:null
    });
    return {
      lead:el('sceneLeadRelation').textContent,
      candidate:el('sceneCandidateStatus').textContent,
      lane:el('sceneLaneStatus').textContent
    };
  })()"""
  assert run_frontend_expression(expression) == {
    "lead": "28.4 m · -1.8 m/s",
    "candidate": "궤적 표시",
    "lane": "데이터 없음 · 3차선 틀",
  }
