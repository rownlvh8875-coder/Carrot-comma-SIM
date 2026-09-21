from __future__ import annotations

import json
from threading import Thread
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest


def sample_run():
  return {"run_id":"sample","label":"샘플","frame_count":2,
    "authority":{"recommendation_authorized":False,"real_vehicle_write":False},
    "evidence_class":"CURRENT_REFERENCE","rows_sha256":"a"*64,
    "frames":[{"index":0,"mono_ns":"1"},{"index":1,"mono_ns":"2"}]}


@pytest.fixture
def server_url():
  from carrot_sim.visual_app_server import create_visual_server
  server=create_visual_server([sample_run()],port=0)
  thread=Thread(target=server.serve_forever,daemon=True);thread.start()
  host,port=server.server_address
  try: yield f"http://{host}:{port}"
  finally: server.shutdown();server.server_close();thread.join(timeout=2)


def get_json(url):
  with urlopen(url,timeout=2) as response:
    return response.status,json.loads(response.read())


def test_server_exposes_health_catalog_and_bounded_frames(server_url):
  assert get_json(server_url+"/healthz")[1]=={"ok":True,"read_only":True}
  assert get_json(server_url+"/api/catalog")[1]["runs"][0]["run_id"]=="sample"
  page=get_json(server_url+"/api/runs/sample/frames?offset=0&limit=1")[1]
  assert len(page["frames"])==1 and page["next_offset"]==1


def test_server_rejects_non_loopback():
  from carrot_sim.visual_app_server import create_visual_server
  with pytest.raises(ValueError,match="loopback"):
    create_visual_server([sample_run()],host="0.0.0.0",port=0)


def test_unknown_run_and_invalid_query_fail_closed(server_url):
  for path in ("/api/runs/missing","/api/runs/sample/frames?limit=2001",
               "/api/runs/sample/frames?offset=0&bogus=1","/api/runs/../secret"):
    with pytest.raises(HTTPError) as caught:
      urlopen(server_url+path,timeout=2)
    assert caught.value.code in {400,404}


def test_server_sets_security_and_cache_headers(server_url):
  with urlopen(server_url+"/api/catalog",timeout=2) as response:
    assert response.headers["Cache-Control"]=="no-store"
    assert response.headers["X-Content-Type-Options"]=="nosniff"


def test_server_exposes_optimization_status_and_report(tmp_path):
  from carrot_sim.visual_app_server import create_visual_server
  campaign=tmp_path/"campaign";campaign.mkdir()
  (campaign/"status.json").write_text(json.dumps({"phase":"report","real_vehicle_write":False}))
  (campaign/"recommendation.json").write_text(json.dumps({"state":"RETAIN_CURRENT","deployment_authorized":False}))
  server=create_visual_server([sample_run()],port=0,optimization_dir=campaign)
  thread=Thread(target=server.serve_forever,daemon=True);thread.start()
  host,port=server.server_address;url=f"http://{host}:{port}"
  try:
    assert get_json(url+"/api/optimization/status")[1]["phase"]=="report"
    assert get_json(url+"/api/optimization/report")[1]["state"]=="RETAIN_CURRENT"
  finally:
    server.shutdown();server.server_close();thread.join(timeout=2)


def test_public_synthetic_catalog_loads_with_safe_authority():
  from pathlib import Path
  from carrot_sim.visual_app_server import load_catalog_file
  root = Path(__file__).resolve().parents[1]
  catalog = load_catalog_file(root / "examples" / "visual_app_catalog.json")
  assert [run["run_id"] for run in catalog] == [
    "synthetic-baseline", "synthetic-candidate"]
  assert all(run["frame_count"] == 3 for run in catalog)
  assert all(run["authority"] == {
    "recommendation_authorized": False, "real_vehicle_write": False}
    for run in catalog)
