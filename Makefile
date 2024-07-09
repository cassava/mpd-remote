SHELL := /bin/bash

export PIPX_HOME := /usr/local/lib/pipx
export PIPX_BIN_DIR := /usr/local/bin

.PHONY: debian-deps
debian-deps:
	apt install \
		sox \
		screen \
		pipx

.PHONY: install enable start restart uninstall
install:
	if [[ -z "$$(command -v play)" ]]; then \
		echo "Error: required executable missing: sox"; \
		false; \
	elif [[ -z "$$(command -v screen)" ]]; then \
		echo "Error: required executable missing: screen"; \
		false; \
	fi
	pipx install .
	install -m644 mpd-remote.service /etc/systemd/system/
	systemctl daemon-reload

enable:
	systemctl enable mpd-remote.service

start:
	systemctl start mpd-remote.service

restart:
	systemctl restart mpd-remote.service

uninstall:
	pipx remove mpd-remote
	systemctl disable mpd-remote.service
	rm /etc/systemd/system/mpd-remote.service
	systemctl daemon-reload
