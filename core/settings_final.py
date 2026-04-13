path = "/var/www/fina-connect/core/settings.py"
with open(path, "r") as f:
    lines = f.readlines()

with open(path, "w") as f:
    for line in lines:
        if line.startswith("ALLOWED_HOSTS ="):
            f.write(
                "ALLOWED_HOSTS = ['limit-connect.com', 'www.limit-connect.com', 'viskovic-group.de', 'www.viskovic-group.de', '85.9.201.204', 'localhost', '127.0.0.1']\n"
            )
        else:
            f.write(line)
