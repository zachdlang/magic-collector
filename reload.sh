#!/bin/bash

cd /var/www/collector && sudo -u zach git pull
cd

echo 'Reloading collector...'
sudo systemctl restart gu-collector
sudo systemctl restart celery-collector