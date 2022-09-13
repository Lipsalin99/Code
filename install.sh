#!/bin/bash -l

if [[ $EUID -ne 0 ]]
then
	echo -e "\e[31m This Script must be run as root user ...\e[0m"
	exit 1
fi

for file in '/opt/tcm/iso/Rohit_Bootable_Label_PowerTools_Centos8.0-Everything.iso' '/opt/tcm/xcat-2.16.1/xcat-core-2.16.1-linux.tar.bz2' '/opt/tcm/xcat-2.16.1/xcat-dep-2.16.1-linux.tar.bz2' '/opt/tcm/otherpkgs.tar.gz'
do
test -f $file
RETVAL=$?
if [[ $RETVAL -ne 0 ]]
then
	echo -e "\e[31m$file file is not present ... \e[0m"
	exit 1
fi
done

read -p "Enter previous mysql root password (password is empty in new installation): " old_mariadb_pass
read -p "Enter new mysql root password: " new_mariadb_pass
#echo "ansible-playbook tcmmaster.yml  --extra-vars 'old_mariadb_pass=\"${old_mariadb_pass}\" new_mariadb_pass=\"${new_mariadb_pass}\"'"


exec &>/opt/tcm/logfile.txt

mkdir /etc/yum.repos.d/backup
mv /etc/yum.repos.d/*.repo /etc/yum.repos.d/backup/

mount -o loop /opt/tcm/iso/Rohit_Bootable_Label_PowerTools_Centos8.0-Everything.iso /mnt/

cd /opt/tcm && tar xvf otherpkgs.tar.gz
createrepo /opt/tcm/otherpkgs

repofile=$(mktemp --tmpdir='/etc/yum.repos.d/' --suffix '.repo' local-XXXXXX)

echo $repofile
cat >$repofile <<'EOF'

[AppStream]
name=AppStream
baseurl=file:///tcmrepo/AppStream/
enabled=1
gpgcheck=0

[BaseOS]
name=BaseOS
baseurl=file:///tcmrepo/BaseOS/
enabled=1
gpgcheck=0

[HA]
name=HA
baseurl=file:///tcmrepo/HighAvailability/
enabled=1
gpgcheck=0

[PowerTools]
name=PowerTools
baseurl=file:///tcmrepo/PowerTools/
enabled=1
gpgcheck=0

[Epel]
name=Epel
baseurl=file:///tcmrepo/Epel/
enabled=1
gpgcheck=0

[otherpkgs]
name=otherpkgs
baseurl=file:///opt/tcm/otherpkgs/
enabled=1
gpgcheck=0


EOF

: "
cat >$repofile <<'EOF'
[Local-BaseOS]
name=CentOS Linux 8 - BaseOS
metadata_expire=-1
gpgcheck=0
enabled=1
baseurl=file:///mnt/BaseOS/
#gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-centosofficial

[Local-AppStream]
name=CentOS Linux 8 - AppStream
metadata_expire=-1
gpgcheck=0
enabled=1
baseurl=file:///mnt/AppStream/
#gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-centosofficial

[Local-epel]
name=CentOS Linux 8 - epel
metadata_expire=-1
gpgcheck=0
enabled=1
baseurl=file:///mnt/epel/
#gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-centosofficial

[Local-PowerTools]
name=CentOS Linux 8 - PowerTools
metadata_expire=-1
gpgcheck=0
enabled=1
baseurl=file:///mnt/PowerTools/
#gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-centosofficial

[otherpkgs]
name=otherpkgs
baseurl=file:///opt/tcm/otherpkgs/
enabled=1
gpgcheck=0


EOF"

yum clean all
echo "installing celery"
yum -y install createrepo ansible httpd rsync mod_ssl perl-JSON python3-devel php redhat-lsb-core rabbitmq-server nmap syslinux bind perl  mariadb-server mariadb perl-CGI tftp
#libselinux-python httpd MySQL-python createrepo mod_ssl perl-JSON PyPAM python2-devel php redhat-lsb-core python-celery rabbitmq-server python-sqlalchemy      perl-Crypt-SSLeay
#rm -f $repofile
#umount /mnt
ansible --version

#echo "ansible-playbook tcmmaster.yml  --extra-vars 'old_mariadb_pass=\"${old_mariadb_pass}\" new_mariadb_pass=\"${new_mariadb_pass}\"'"

cd /opt/tcm/ansible && ansible-playbook tcmmaster.yml --extra-vars 'old_mariadb_pass=\"'${old_mariadb_pass}'\" new_mariadb_pass=\"'${new_mariadb_pass}'\"'


#need to do it in new shell..so this below 2 commandsd not executed.
#mv /opt/xcat/lib/perl/xCAT/data/discinfo.pm /opt/discinfo.pm.orig
#cp /opt/tcm/discinfo.pm /opt/xcat/lib/perl/xCAT/data/discinfo.pm
#These below two lines added by Rohit on 04SEPT2018

cp -f /opt/tcm/celery.service /etc/systemd/system/celery.service
cp -f /opt/tcm/tcm.service /etc/systemd/system/tcm.service
# echo "<script>location.href=\"tcm/main.py\"</script>" > /var/www/html/index.html
#make  celery service 
cp  /opt/tcm/celery.service /usr/lib/systemd/system/celery.service
cp  /opt/tcm/gsync.service /usr/lib/systemd/system/gsync.service
cp  /opt/tcm/tcm.service /usr/lib/systemd/system/tcm.service

mkdir -p /etc/conf.d
cp  /opt/tcm/celery /etc/conf.d/
cp -rvf   /opt/tcm/cron_d/*   /etc/cron.d/  
mkdir -p  /var/log/celery
touch /var/log/celery/celery.log
mkdir -p /apps/scratch/source
mkdir -p /apps/scratch/compile
systemctl restart rabbitmq-server.service
# /etc/init.d/rabbitmq-server start
systemctl enable rabbitmq-server
systemctl start celery
systemctl enable celery
systemctl start tcm
systemctl enable tcm
systemctl start gsync
systemctl enable gsync

# copy some missing file 
cp -frv /opt/tcm/compute.centos8.tmpl /opt/xcat/share/xcat/install/centos/
cp /usr/share/syslinux/menu.c32 /tftpboot/
cp /usr/share/syslinux/ldlinux.c32 /tftpboot/
cp /usr/share/syslinux/libutil.c32 /tftpboot/
cp /usr/share/syslinux/libcom32.c32 /tftpboot/

cp -frv /opt/tcm/post.rhels7 /opt/xcat/share/xcat/install/scripts/post.rhels7
# #yum install ntp -y
# #systemctl stop ntpd.service
# #systemctl start ntpd.service
# #systemctl enable ntpd.service


# # bicop-1.0rc2.tar.gz
# # netifaces-0.10.9.tar.gz
