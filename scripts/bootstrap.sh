#!/usr/bin/env bash
# Turn this template into a real project: replace the placeholders, once.
set -euo pipefail
cd "$(dirname "$0")/.."

read -r -p "ชื่อโปรเจกต์ (เช่น Acme Portal): " PROJECT
read -r -p "ชื่อแพ็กเกจ/โฟลเดอร์โค้ดหลัก (เช่น acme): " PKG
read -r -p "path ที่เก็บโค้ดหลัก [$(pwd)]: " BACKEND; BACKEND="${BACKEND:-$(pwd)}"
read -r -p "path ที่เก็บโค้ดหน้าเว็บ (เว้นว่างถ้าไม่มี): " FRONTEND

[ -z "$PROJECT" ] && { echo "ต้องมีชื่อโปรเจกต์" >&2; exit 1; }
[ -z "$PKG" ] && { echo "ต้องมีชื่อแพ็กเกจ" >&2; exit 1; }

FILES=$(grep -rl '<PROJECT>\|<PACKAGE>\|<BACKEND_REPO_PATH>\|<FRONTEND_REPO_PATH>\|<FRONTEND_REPO>' \
        .claude doc docs CLAUDE.md README.md 2>/dev/null || true)
[ -z "$FILES" ] && { echo "ไม่พบตัวยึด — เหมือนจะ bootstrap ไปแล้ว"; exit 0; }

python3 - "$PROJECT" "$PKG" "$BACKEND" "$FRONTEND" <<'PY'
import pathlib, sys, re
project, pkg, backend, frontend = sys.argv[1:5]
subs = {
    '<PROJECT>': project,
    '<PACKAGE>': pkg,
    '<BACKEND_REPO_PATH>': backend,
    '<FRONTEND_REPO_PATH>': frontend or '(ไม่มีที่เก็บโค้ดหน้าเว็บ)',
    '<FRONTEND_REPO>': pathlib.Path(frontend).name if frontend else '(none)',
}
n = 0
for root in ('.claude', 'doc', 'docs'):
    for p in pathlib.Path(root).rglob('*'):
        if p.is_file() and p.suffix in {'.md', '.py', '.json', '.yaml', '.yml'}:
            s = p.read_text(encoding='utf-8'); o = s
            for a, b in subs.items(): s = s.replace(a, b)
            if s != o: p.write_text(s, encoding='utf-8'); n += 1
for name in ('CLAUDE.md', 'README.md'):
    p = pathlib.Path(name)
    if p.exists():
        s = p.read_text(encoding='utf-8'); o = s
        for a, b in subs.items(): s = s.replace(a, b)
        if s != o: p.write_text(s, encoding='utf-8'); n += 1
print(f"แทนที่ตัวยึดใน {n} ไฟล์")
PY

mkdir -p ~/.claude/approvals && touch ~/.claude/approvals/registry.jsonl
echo
echo "เรียบร้อย — ทะเบียนอนุมัติอยู่ที่ ~/.claude/approvals/registry.jsonl (มนุษย์เท่านั้นที่เขียนได้)"
echo "ขั้นต่อไป: เติมหัวข้อที่ยังเป็น <...> ใน CLAUDE.md แล้วเปิด Claude Code ในโฟลเดอร์นี้"
