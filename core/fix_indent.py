path = "/var/www/fina-connect/core/settings.py"
with open(path, "r") as f:
    lines = f.readlines()

new_lines = []
skip = False
for line in lines:
    if "ALLOWED_HOSTS =" in line:
        new_lines.append("ALLOWED_HOSTS = [\n")
        new_lines.append("    'limit-connect.com', 'www.limit-connect.com',\n")
        new_lines.append("    'viskovic-group.de', 'www.viskovic-group.de',\n")
        new_lines.append("    '85.9.201.204', 'localhost', '127.0.0.1',\n")
        new_lines.append("]\n")
        skip = True
    elif skip and "]" in line:
        skip = False
        continue
    elif not skip:
        new_lines.append(line)

with open(path, "w") as f:
    f.writelines(new_lines)
