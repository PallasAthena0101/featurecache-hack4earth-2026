import subprocess,sys,json
from pathlib import Path
from datetime import datetime,timezone
result=subprocess.run([sys.executable,'-m','unittest','discover','-v'],capture_output=True,text=True)
Path('tests.txt').write_text(result.stdout+result.stderr)
assert result.returncode==0,result.stderr
subprocess.run([sys.executable,'benchmark_lifecycle.py','--protocol','protocol.json','--output','results.json'],check=True)
Path('finished.json').write_text(json.dumps(dict(utc=datetime.now(timezone.utc).isoformat(),state='complete',tests_passed=True)))
