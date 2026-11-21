"""Compile one immutable empty contract per expression across the trusted snapshot."""
from batch import *
from compile_repair.toolchain.solc import load_trusted_compilers, version_tuple
from compile_repair.toolchain.slither import check_profile

compilers, _, trust = load_trusted_compilers()
assert len(compilers) == 92
versions = sorted(compilers, key=version_tuple)
profile = check_profile('production')
folder = LOCAL/'pragma_oracle'
folder.mkdir(parents=True, exist_ok=False)
forms = ['0.5','0.4.x','0.5.X','0.5.*','0','0.x','0.X','0.*','0.x.x']
operators = ['', '=', '^', '~', '>', '>=', '<', '<=']
expressions = [op+form for form in forms for op in operators]
expressions.extend(['~0.4', '^0.5 <0.6', '>=0.5 <0.8.4','0.4.X','>= 0.4.x <=0.5.*','^0.5.17','=0.8.0','^0.0','~0.0','0.0.x'])
accepted = {}
count = 0
start = time.monotonic()
with (folder/'invocations.jsonl').open('x') as log:
    for seq, expr in enumerate(expressions):
        source = folder/('case_%03d.sol' % seq)
        source.write_text('pragma solidity '+expr+'; contract Empty {}\n')
        accepted[expr] = []
        for version in versions:
            c = compilers[version]
            command = [c.path, str(source)]
            tick = time.monotonic()
            cp = subprocess.run(command, capture_output=True, timeout=30)
            stderr = cp.stderr.decode('utf8', 'replace')
            rejected = 'requires different compiler version' in stderr.lower()
            row = dict(expression=expr, version=version, executable_sha256=c.sha256, command=command, source_sha256=sha(source.read_bytes()), returncode=cp.returncode, cost_usd=0, requires_different_version=rejected, error_first_line=next(iter(stderr.splitlines()),None), stderr=stderr, elapsed_seconds=time.monotonic()-tick)
            log.write(json.dumps(row)+'\n')
            if cp.returncode and not rejected:
                log.flush()
                raise RuntimeError((expr,version,'unexpected solc diagnostic',stderr[:320]))
            if not rejected:
                accepted[expr].append(version)
            count += 1
save('pragma_oracle.json',dict(expressions=accepted, versions=versions, calls=count, invocations=str(folder/'invocations.jsonl'), invocations_sha256=sha((folder/'invocations.jsonl').read_bytes()), elapsed_seconds=time.monotonic()-start))
print(count, len(expressions))
