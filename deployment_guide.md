# Linux Deployment Guide for AbraGo PFE

This guide explains how to deploy the AbraGo PFE Django application in a production environment on a Linux Server (Ubuntu/Debian).

---

## 1. System Requirements & Preparation

Update your system packages and install the system prerequisites:
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3-pip python3-venv nginx git curl libpq-dev -y
```

---

## 2. Project Setup

### Clone the Repository
Clone your project repository into `/var/www/`:
```bash
cd /var/www
sudo git clone <your-repo-url> abrago
sudo chown -R $USER:$USER abrago
cd abrago
```

### Initialize the Virtual Environment & Dependencies
Create and activate the virtual environment, then install requirements:
```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install django gunicorn pillow qrcode
```

### Database & Static Files
Configure the migrations and collect static files:
```bash
python manage.py makemigrations
python manage.py migrate
python manage.py collectstatic --no-input
```

---

## 3. SQLite Database Directory & Media Permissions

Since SQLite is a file-based database, the Nginx/Gunicorn user (`www-data`) must have read/write permissions on both the database file (`db.sqlite3`) and its containing folder:
```bash
sudo chown -R :www-data /var/www/abrago
sudo chmod 775 /var/www/abrago
sudo chmod 664 /var/www/abrago/db.sqlite3
```
Additionally, the static folder (specifically `static/qr_codes/`) needs write permissions so Gunicorn can save new QR code files:
```bash
sudo chmod -R 775 /var/www/abrago/static
```

---

## 4. Configuring Gunicorn (WSGI Application Server)

We will use systemd to manage Gunicorn as a system service.

### Create systemd Gunicorn Socket
Create a socket unit:
```bash
sudo nano /etc/systemd/system/gunicorn.socket
```
Paste the following content:
```ini
[Unit]
Description=gunicorn socket

[Socket]
ListenStream=/run/gunicorn.sock

[Install]
WantedBy=sockets.target
```

### Create systemd Gunicorn Service
Create the service unit:
```bash
sudo nano /etc/systemd/system/gunicorn.service
```
Paste the following content:
```ini
[Unit]
Description=gunicorn daemon
Requires=gunicorn.socket
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/abrago
ExecStart=/var/www/abrago/venv/bin/gunicorn \
          --access-logfile - \
          --workers 3 \
          --bind unix:/run/gunicorn.sock \
          abrago.wsgi:application

[Install]
WantedBy=multi-user.target
```

### Start and Enable Gunicorn
```bash
sudo systemctl start gunicorn.socket
sudo systemctl enable gunicorn.socket
sudo systemctl daemon-reload
sudo systemctl restart gunicorn
```

---

## 5. Configuring Nginx (Reverse Proxy)

Create an Nginx configuration file for your server:
```bash
sudo nano /etc/nginx/sites-available/abrago
```
Paste the following config block (replace `your_domain_or_ip` with your domain/IP):
```nginx
server {
    listen 80;
    server_name your_domain_or_ip;

    location = /favicon.ico { access_log off; log_not_found off; }
    
    location /static/ {
        root /var/www/abrago;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/run/gunicorn.sock;
    }
}
```

### Enable Nginx Server Block
```bash
sudo ln -s /etc/nginx/sites-available/abrago /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

## 6. Securing with SSL (Let's Encrypt)

Install Certbot for Nginx to enable HTTPS:
```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d your_domain_or_ip
```
Follow the interactive prompts to enable automatic HTTP-to-HTTPS redirects.
