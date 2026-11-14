"""Nachladen der Commons-Dateien mit Pausen (429). python -I fetch_commons_retry.py <corpus_dir>"""
import json, pathlib, sys, time, urllib.error
sys.argv = [sys.argv[0], sys.argv[1]]
import importlib.util
spec = importlib.util.spec_from_file_location("fc", str(pathlib.Path(__file__).with_name("fetch_corpus.py")))
fc = importlib.util.module_from_spec(spec); spec.loader.exec_module(fc)
for k, u in fc.COMMONS.items():
    if (fc.WAV / f"{k}.wav").exists():
        continue
    for i in range(6):
        try:
            fc.commons(k, u); break
        except urllib.error.HTTPError as e:
            print(k, e.code, flush=True); time.sleep(20 * (i + 1))
    time.sleep(8)
