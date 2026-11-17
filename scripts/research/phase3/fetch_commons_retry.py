"""Nachladen der Commons-Dateien mit Pausen (429).

python -I fetch_commons_retry.py [--ffmpeg PFAD] <corpus_dir>
ffmpeg kommt aus --ffmpeg, sonst aus der Umgebungsvariable AVS_FFMPEG, sonst aus PATH.
"""

import importlib.util
import pathlib
import sys
import time
import urllib.error

spec = importlib.util.spec_from_file_location("fc", str(pathlib.Path(__file__).with_name("fetch_corpus.py")))
if spec is None or spec.loader is None:
    raise SystemExit("fetch_corpus.py not found next to this script")
fc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fc)

corpus = fc.open_corpus(sys.argv[1:])
for k, u in fc.COMMONS.items():
    if (corpus.wav / f"{k}.wav").exists():
        continue
    for i in range(6):
        try:
            fc.commons(corpus, k, u)
            break
        except urllib.error.HTTPError as e:
            print(k, e.code, flush=True)
            time.sleep(20 * (i + 1))
    time.sleep(8)
