#!/bin/bash
yum install -y httpd
systemctl enable httpd
systemctl start httpd
echo "<h1>Self-Healing Demo Server</h1>" > /var/www/html/index.html
