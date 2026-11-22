# R1 - MikroTik CHR 7.24.6 - minimal bootstrap (management + SSH only)
# First login: admin / (empty password). RouterOS then asks for a new password:
# enter the lab password (same value as NET_PASSWORD in .env).
# Paste ONE line at a time into the GNS3 console.
/system identity set name=R1-MikroTik
/ip address add address=192.168.100.11/24 interface=ether1 comment=Management
/ip service enable ssh
/ip service set ssh port=22
/ip address print
