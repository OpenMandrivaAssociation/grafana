%global           GRAFANA_USER %{name}
%global           GRAFANA_GROUP %{name}
%global           GRAFANA_HOME %{_datadir}/%{name}

Name:		grafana
Version:	6.2.1
Release:	1
Summary:	Metrics dashboard and graph editor
Group:		Development/Other
License:	ASL 2.0
URL:		https://grafana.com
Source0:	https://github.com/grafana/grafana/archive/v%{version}.tar.gz
BuildRequires:	golang
BuildRequires:	nodejs

%description
Grafana is an open source, feature rich metrics dashboard and graph editor
for Graphite, Elasticsearch, OpenTSDB, Prometheus and InfluxDB.

%prep
%setup -q
mkdir -p ../src/github.com/grafana/grafana
mv $(ls | grep -v "^src$") ../src/github.com/grafana/grafana/.

%build
%define gobuild(o:) go build -ldflags "${LDFLAGS:-} -B 0x$(head -c20 /dev/urandom|od -An -tx1|tr -d ' \\n')" -a -v -x %{?**};
pushd ../src/github.com/grafana/grafana
#go get golang.org/x/sync/errgroup
#GOPATH="${PWD}:%{gopath}" make deps-go
#make deps-go
#GOPATH="${PWD}:%{gopath}" make build-go
#make build-go
export GOPATH=%{_builddir}:%{gopath}
%gobuild -o grafana-cli ./pkg/cmd/grafana-cli
%gobuild -o grafana-server ./pkg/cmd/grafana-server

export NPM_CONFIG_PREFIX="%{_builddir}/npm"
export PATH+=":$NPM_CONFIG_PREFIX/bin"
npm install -g yarn
yarn install --pure-lockfile --no-progress
npm run build release
popd



%install
pushd ../src/github.com/grafana/grafana
install -p -D -m 755 %{name}-server %{buildroot}/%{_sbindir}/%{name}-server
install -p -D -m 755 %{name}-cli %{buildroot}/%{_sbindir}/%{name}-cli

sed -ri 's,^(\s*data\s*=).*,\1 /var/lib/grafana,' conf/defaults.ini
sed -ri 's,^(\s*plugins\s*=).*,\1 /var/lib/grafana/plugins,' conf/defaults.ini
sed -ri 's,^(\s*provisioning\s*=).*,\1 /var/lib/grafana/conf/provisioning,' conf/defaults.ini
sed -ri 's,^(\s*logs\s*=).*,\1 /var/log/grafana,' conf/defaults.ini

install -p -D -m 640 conf/sample.ini %{buildroot}/%{_sysconfdir}/%{name}/%{name}.ini
install -p -D -m 640 conf/ldap.toml %{buildroot}/%{_sysconfdir}/%{name}/ldap.toml

install -p -D -m 644 packaging/rpm/systemd/grafana-server.service %{buildroot}%{_unitdir}/grafana-server.service
install -p -D -m 644 packaging/rpm/sysconfig/grafana-server %{buildroot}/%{_sysconfdir}/sysconfig/grafana-server

install -d %{buildroot}%{_datadir}/%{name}
install -d %{buildroot}%{_tmpfilesdir}

for i in scripts conf public tools; do
    cp -r $i %{buildroot}%{_datadir}/%{name}
done

popd

# daemon run pid file config for using tmpfs
install -d %{buildroot}%{_sharedstatedir}/%{name}/plugins
install -d %{buildroot}%{_logdir}/%{name}/

rm -rf %{buildroot}/%{_datadir}/%{name}/scripts/build/release_publisher/testdata/

echo "d %{_rundir}/%{name} 0755 %{GRAFANA_USER} %{GRAFANA_GROUP} -" \
    > %{buildroot}%{_tmpfilesdir}/%{name}.conf


# check me when local build
# jot possible on koji
# network not available there
%check
cd %{_builddir}/src/github.com/grafana/grafana
export GOPATH=%{_builddir}:%{gopath}
rm -f pkg/services/provisioning/dashboards/file_reader_linux_test.go
#GO111MODULE=on go test -v ./pkg/...

%pre
getent group %{GRAFANA_GROUP} >/dev/null || groupadd -r %{GRAFANA_GROUP}
getent passwd %{GRAFANA_USER} >/dev/null || \
    useradd -r -g %{GRAFANA_GROUP} -d %{GRAFANA_HOME} -s /sbin/nologin \
    -c "%{GRAFANA_USER} user account" %{GRAFANA_USER}
exit 0

%post
%systemd_post %{name}-server.service

%preun
%systemd_preun %{name}-server.service

%postun
%systemd_postun_with_restart %{name}-server.service

%files
# binaries
%{_sbindir}/%{name}-server
%{_sbindir}/%{name}-cli

# config files
%dir %{_sysconfdir}/%{name}
%config(noreplace) %attr(644, root, %{GRAFANA_GROUP}) %{_sysconfdir}/%{name}/grafana.ini
%config(noreplace) %attr(644, root, %{GRAFANA_GROUP}) %{_sysconfdir}/%{name}/ldap.toml
%config(noreplace) %{_sysconfdir}/sysconfig/grafana-server

# Grafana configuration to dynamically create /run/grafana/grafana.pid on tmpfs
%{_tmpfilesdir}/%{name}.conf

# config database directory and plugins (actual db files are created by grafana-server)
%attr(-, %{GRAFANA_USER}, %{GRAFANA_GROUP}) %dir %{_sharedstatedir}/%{name}
%attr(-, %{GRAFANA_USER}, %{GRAFANA_GROUP}) %dir %{_sharedstatedir}/%{name}/plugins

# shared directory and all files therein
%dir %{_datadir}/%{name}
%{_datadir}/%{name}/public
%{_datadir}/%{name}/scripts
%{_datadir}/%{name}/tools
%dir %{_datadir}/%{name}/conf
%attr(-, root, %{GRAFANA_GROUP}) %{_datadir}/%{name}/conf/*

# systemd service file
%{_unitdir}/grafana-server.service

# log directory - grafana.log is created by grafana-server, and it does it's own log rotation
%attr(0755, %{GRAFANA_USER}, %{GRAFANA_GROUP}) %dir %{_localstatedir}/log/%{name}
