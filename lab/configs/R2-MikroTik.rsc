# 2026-11-22 01:02:21 by RouterOS 7.24.6
# system id = 3WWC6wGvfYG
#
/interface ethernet
set [ find default-name=ether1 ] disable-running-check=no
set [ find default-name=ether2 ] disable-running-check=no
set [ find default-name=ether3 ] disable-running-check=no
set [ find default-name=ether4 ] disable-running-check=no
set [ find default-name=ether5 ] disable-running-check=no
set [ find default-name=ether6 ] disable-running-check=no
set [ find default-name=ether7 ] disable-running-check=no
set [ find default-name=ether8 ] disable-running-check=no
/ip address
add address=192.168.100.12/24 comment=Management interface=ether1 network=\
    192.168.100.0
/ip dhcp-client
add interface=ether1 name=client1
/system identity
set name=R2-MikroTik
