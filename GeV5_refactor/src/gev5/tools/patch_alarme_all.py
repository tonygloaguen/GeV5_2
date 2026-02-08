import re, glob, shutil

def patch_file(p):
    src = open(p, encoding="utf-8", errors="ignore").read()
    out = src

    # 1) Armement 5s
    if "def run(self):" in out and "ARM_DELAY_S" not in out.split("def run(self):",1)[1][:200]:
        out = re.sub(r"def run\\(self\\):",
                     "def run(self):\n        ARM_DELAY_S = 5\n        boot_time = time.time()",
                     out)
        out = re.sub(r"while\\s+self\\.D1_ON\\s*:",

                     out)

    # 2) Sécurité positive : 0 = cellule active
    out = re.sub(r"\\b1\\s+in\\s+self\\.liste\\b", "0 in self.liste", out)
    out = re.sub(r"\\b1\\s+not\\s+in\\s+self\\.liste\\b", "0 not in self.liste", out)
    out = re.sub(r"cellule_active\\s*=\\s*0\\s*in\\s*self\\.liste", "cellule_active = 0 in self.liste", out)

    # (optionnel) petit log pour chaque module
    out = re.sub(
        r"(self\\.liste\\s*=\\s*\\[.*?\\]\\s*)",

        out, flags=re.S
    ).replace("%(name)s", p.split('/')[-1].replace('.py',''))

    if out != src:
        shutil.copy2(p, p + ".bak")
        open(p, "w", encoding="utf-8").write(out)
        print("Patched:", p)
    else:
        print("Unchanged:", p)

for f in sorted(glob.glob("alarme_*.py")):
    patch_file(f)
print("OK. Redémarre le moteur.")
