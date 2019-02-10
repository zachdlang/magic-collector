# magic-collector

## Gunicorn Setup
1. Set up a symlink for the service file, so Gunicorn can be automatically started & reloaded.
`ln -s <Location>/collector/gu-app.service /etc/systemd/system/gu-collector.service`
1. Activate the service file, enable it at boot/resart, and start the app.
```
systemctl daemon-reload
systemctl enable gu-collector
systemctl start gu-collector
```
