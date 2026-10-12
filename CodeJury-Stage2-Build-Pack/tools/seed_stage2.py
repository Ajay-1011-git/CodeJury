"""Seed only shared Stage 2 contract/interface files into an audited original Stage1 repo.

Dry-run by default. Does not implement or run CodeJury and does not touch runtime data.
"""
from pathlib import Path
import argparse,hashlib,json,shutil

PACK=Path(__file__).resolve().parents[1]
OLD='5f760939e1fbf34cb7613a38f9476595d23a829089e8e557adc015cb0168f0df'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',type=Path,required=True);p.add_argument('--apply',action='store_true');a=p.parse_args()
 repo=a.repo.resolve()
 if not repo.is_dir():raise SystemExit('Select an existing audited repository directory.')
 original=repo/'contracts/stage1-api.schema.json'
 if not original.is_file() or sha(original)!=OLD:raise SystemExit('Expected the known ORIGINAL Stage1 contract. Audit missing/different schemas; no automatic overwrite.')
 for parent in [repo/'contracts',repo/'backend',repo/'reference',repo/'integration']:
  if parent.is_symlink():raise SystemExit('Refusing symlink in shared seed destination.')
 for pth in (repo/'contracts').rglob('*'):
  if pth.is_symlink():raise SystemExit('Refusing symlink inside contracts.')
 files={
  'contracts/stage2.schema.json':PACK/'contracts/stage2.schema.json',
  'contracts/shared/stage2_ports.py':PACK/'contracts/shared/stage2_ports.py',
  'backend/src/codejury/stage2_ports.py':PACK/'contracts/shared/stage2_ports.py',
  'contracts/legacy/stage1-v1-api.schema.json':PACK/'reference/stage1-v1-api.schema.json',
 }
 # Keep the original contracts/SHA256SUMS unchanged; Stage2 has its own adjacent checksum.
 files['contracts/STAGE2-SHA256SUMS']=PACK/'contracts/SHA256SUMS'
 for source in (PACK/'reference').iterdir():
  if source.is_file():files['reference/stage2/'+source.name]=source
 readme='Stage2 integration custodian: inspect real dependencies, seed compatible common constraints, record the common commit, then wire owner factories at E checkpoints. No automatic service starts.\n'
 targetreadme=repo/'integration/stage2/README.md'
 for ancestor in [targetreadme,*targetreadme.parents]:
  if ancestor==repo:break
  if ancestor.is_symlink():raise SystemExit('Refusing symlink in integration README path.')
 if targetreadme.exists() and targetreadme.read_text()!=readme:raise SystemExit('Integration README already differs; inspect it before seeding.')
 for relative,source in files.items():
  target=repo/relative
  if target.is_symlink():raise SystemExit('Refusing symlink seed target: '+relative)
  for ancestor in target.parents:
   if ancestor==repo:break
   if ancestor.is_symlink():raise SystemExit('Refusing symlink ancestor: '+str(ancestor))
  if target.exists() and (not target.is_file() or target.read_bytes()!=source.read_bytes()):raise SystemExit('Seed target already differs: '+relative)
 # Stage1 fixtures remain in place; the application/checker loads the explicitly versioned Stage2 directory.
 fixture_dest=repo/'contracts/stage2-fixtures'
 if fixture_dest.is_symlink():raise SystemExit('Refusing symlink Stage2 fixture directory.')
 for source in (PACK/'contracts/fixtures').iterdir():
  target=fixture_dest/source.name
  if target.is_symlink():raise SystemExit('Refusing fixture symlink.')
  if target.exists() and (not target.is_file() or target.read_bytes()!=source.read_bytes()):raise SystemExit('Stage2 fixture already differs: '+source.name)
 if fixture_dest.exists():
  expected={x.name for x in (PACK/'contracts/fixtures').iterdir()};actual={x.name for x in fixture_dest.iterdir()}
  if actual-expected:raise SystemExit('Unexpected extra Stage2 fixture files; inspect manually.')
 plan={'status':'dry_run','repo':str(repo),'schema_sha256':sha(PACK/'contracts/stage2.schema.json'),'writes':list(files)+['contracts/stage2-fixtures/**','integration/stage2/README.md'],
       'preserves':['contracts/stage1-api.schema.json','contracts/SHA256SUMS','contracts/fixtures/**','all original application and runtime data']}
 if not a.apply:print(json.dumps(plan,indent=2));return
 for relative,source in files.items():
  target=repo/relative;target.parent.mkdir(parents=True,exist_ok=True)
  if not target.exists():shutil.copyfile(source,target)
 fixture_dest.mkdir(parents=True,exist_ok=True)
 for source in (PACK/'contracts/fixtures').iterdir():
  target=fixture_dest/source.name
  if not target.exists():shutil.copyfile(source,target)
 targetreadme.parent.mkdir(parents=True,exist_ok=True)
 if not targetreadme.exists():targetreadme.write_text(readme)
 print(json.dumps({'status':'seeded','schema_sha256':sha(repo/'contracts/stage2.schema.json'),'next':'Review Git diff, seed actual common constraints/package discovery, commit once, then both branch.'},indent=2))
if __name__=='__main__':main()
