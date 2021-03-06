.PHONY: install enable start restart uninstall
install:
	if [[ -z "$$(command -v play)" ]]; then \
		echo "Error: required executable missing: sox"; \
		false; \
	elif [[ -z "$$(command -v screen)" ]]; then \
		echo "Error: required executable missing: screen"; \
		false; \
	fi
	pip install .
	install -m644 mpd-remote.service /etc/systemd/system/
	systemctl daemon-reload

enable:
	systemctl enable mpd-remote.service

start:
	systemctl start mpd-remote.service

restart:
	systemctl restart mpd-remote.service

uninstall:
	pip remove mpd-remote
	systemctl disable mpd-remote.service
	rm /etc/systemd/system/mpd-remote.service
	systemctl daemon-reload
