SERVICE := happy-birthday-gdpr
DESTDIR ?= dist_root
SERVICEDIR ?= /srv/$(SERVICE)

GO ?= go
export GOFLAGS ?= -mod=vendor

.PHONY: all
all: happy-birthday-gdpr

happy-birthday-gdpr: $(filter-out bindata.go, $(wildcard *.go)) $(wildcard templates/* static/*) go.mod go.sum
	go generate generate.go
	go build -o $@

install: all
	install -d $(DESTDIR)$(SERVICEDIR)
	install -m 644 misc/README.vulnbox $(DESTDIR)$(SERVICEDIR)/README
	install -d $(DESTDIR)$(SERVICEDIR)/bin
	install happy-birthday-gdpr $(DESTDIR)$(SERVICEDIR)/bin/
	install -d $(DESTDIR)/etc/systemd/system
	install -m 644 misc/happy-birthday-gdpr-setup.service $(DESTDIR)/etc/systemd/system/
	install -m 644 misc/happy-birthday-gdpr.service $(DESTDIR)/etc/systemd/system/
	install -d $(DESTDIR)$(SERVICEDIR)/src
	install -m 644 misc/Makefile.vulnbox $(DESTDIR)$(SERVICEDIR)/src/Makefile
	install -m 644 *.go go.mod go.sum $(DESTDIR)$(SERVICEDIR)/src/
	rm $(DESTDIR)$(SERVICEDIR)/src/generate.go
	cp -r vendor/ $(DESTDIR)$(SERVICEDIR)/src/

.PHONY: clean
clean:
	$(RM) happy-birthday-gdpr
	$(RM) bindata.go
	$(RM) -r dist_root
