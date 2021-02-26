.PHONY: attach
attach:
	screen -x FlircDenonHMI

.PHONY: install-deps
install-deps:
	pacman -S --needed python-pip python-mpd2 sox bash
	pip install google_speech

.PHONY: install
install:
	install -m 755 flirc-denon-hmi /usr/local/bin
	install -m 644 flirc-denon-hmi.service /etc/systemd/system/
	systemctl daemon-reload

.PHONY: enable
enable:
	systemd enable flirc-denon-hmi.service

.PHONY: restart
restart:
	systemctl restart flirc-denon-hmi.service

.PHONY: start
start:
	-systemctl stop getty@tty1.service
	systemctl start flirc-denon-hmi.service
