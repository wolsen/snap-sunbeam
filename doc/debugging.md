# Debugging microstack

microstack brings together a number of seperate technologies. This guide attempts to show where to start looking.

## Microk8s

Microk8s has its own [debugging guide](https://microk8s.io/docs/troubleshooting) which is more in depth. Below are some commands which are oftern useful.

Check that microk8s is up and happy
```
microk8s.status
```

To investigate problems with downloading images etc use the microk8s api

```
microk8s.kubectl describe -n openstack pods
```

## Charms

Microstack install the charms in a model called **openstack** in microk8s. The charms status can be seen in the normal way:

```
juju status -m openstack
```

The charms logs can be seen with the debug-log tool

```
juju debug-log -m openstack --replay
```

Logs for each service can be obtained from the workload containers

```
juju ssh --model openstack --container glance-api glance/0 "tar cvf /tmp/glance-logs.tar var/log"
juju scp --model openstack --container glance-api glance/0:/tmp/glance-logs.tar ./glance-logs.tar
```

It is possible to ssh to the container running a particular service. For example if there were issues with the nova api service first run `juju status` to see what nova units are present. If a `nova/0` unit is present the next step is to list the containers associated with the unit.

```
UNIT_NAME=nova/0
POD_NAME=$(echo $UNIT_NAME | sed -e 's!/!-!')
kubectl get pods -n openstack $POD_NAME -o jsonpath='{.spec.containers[*].name}' 
charm nova-api nova-conductor nova-scheduler
```

This shows containers *charm*, *nova-api*, *nova-conductor* and  *nova-scheduler*. The *charm* container runs the juju charm code the other containers are running seperate nova services. Juju providees a shell in any of these containers:

```
juju ssh -m openstack --container nova-api nova/0
```

Warning: Do not make changes inside the container as they are likely to be reverted by the charm or lost when the pod is replaced.

## Microstack commands

The microstack cli takes a **-v** flag which will give extra debug and should help identify any issues.

```microstack -v bootstrap```


## Hypervisor Systemd services

The *openstack-hypervisor* snap includes a number of systemd services. During the microstack bootstrap and configure stages the `snap.openstack-hypervisor.hypervisor-config-service` service is of most interest. 

```
snap.openstack-hypervisor.hypervisor-config-service
snap.openstack-hypervisor.libvirtd
snap.openstack-hypervisor.neutron-ovn-metadata-agent
snap.openstack-hypervisor.nova-api-metadata
snap.openstack-hypervisor.nova-compute
snap.openstack-hypervisor.ovn-controller
snap.openstack-hypervisor.ovs-vswitchd
snap.openstack-hypervisor.ovsdb-server
snap.openstack-hypervisor.virtlogd
```

## Terraform files

microstack uses terraform to manage resources on the deployed cloud. The terraform files are in these locations:

```
${HOME}/snap/microstack/common/etc/configure
/snap/microstack/current/etc/configure
```

Logs from the terraform run can also be found in `${HOME}/snap/microstack/common/etc/configure`.


## Networking

### Localhost only networking

By default the guests will only be accessable from the host on which microstack is installed. In the following example the floating external network cidr is the default *10.20.20.0/24*. 

A route on the host directs traffic for the external network to br-ex

```
ip route | grep 10.20.20
10.20.20.0/24 dev br-ex proto kernel scope link src 10.20.20.1
```

The br-ex bridge has this ip

```
ip addr show br-ex
13: br-ex: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UNKNOWN group default qlen 1000
    link/ether 16:90:59:d9:f2:43 brd ff:ff:ff:ff:ff:ff
    inet 10.20.20.1/24 scope global br-ex
       valid_lft forever preferred_lft forever
    inet6 fe80::1490:59ff:fed9:f243/64 scope link 
       valid_lft forever preferred_lft forever
```

The commands below show that the guest test-server has a private ip 192.168.122.80 which is assigned to port 0208cc16-0197-4079-8701-017609be8f57
```
openstack server list --all-projects
+--------------------------------------+-------------+--------+-------------------------------------------+--------------+----------+
| ID                                   | Name        | Status | Networks                                  | Image        | Flavor   |
+--------------------------------------+-------------+--------+-------------------------------------------+--------------+----------+
| d274bb29-6a3f-4ad6-ad2f-eae739bfbdd4 | test-server | ACTIVE | demo-network=10.20.20.111, 192.168.122.80 | ubuntu-jammy | m1.small |
+--------------------------------------+-------------+--------+-------------------------------------------+--------------+----------+

openstack port list | grep 192.168.122.80
| 0208cc16-0197-4079-8701-017609be8f57 |      | fa:16:3e:54:08:48 | ip_address='192.168.122.80', subnet_id='b2472dfb-d2e1-4a90-871d-ca4b47ed2209' | ACTIVE |
```

This port coralates with a tap device (tap0208cc16-01) which is plugged into br-int. br-int and br-ex are patched together.

```
sudo openstack-hypervisor.ovs-vsctl show 
2735d721-aadc-43fa-9323-b9869eb03824
    Bridge br-int
        fail_mode: secure
        datapath_type: system
        Port tap8c8b5673-c0
            Interface tap8c8b5673-c0
        Port br-int
            Interface br-int
                type: internal
        Port tap0208cc16-01
            Interface tap0208cc16-01
        Port patch-br-int-to-provnet-27a7f01a-7fc0-424f-86ea-acb34937cb7e
            Interface patch-br-int-to-provnet-27a7f01a-7fc0-424f-86ea-acb34937cb7e
                type: patch
                options: {peer=patch-provnet-27a7f01a-7fc0-424f-86ea-acb34937cb7e-to-br-int}
    Bridge br-ex
        datapath_type: system
        Port br-ex
            Interface br-ex
                type: internal
        Port patch-provnet-27a7f01a-7fc0-424f-86ea-acb34937cb7e-to-br-int
            Interface patch-provnet-27a7f01a-7fc0-424f-86ea-acb34937cb7e-to-br-int
                type: patch
                options: {peer=patch-br-int-to-provnet-27a7f01a-7fc0-424f-86ea-acb34937cb7e}
    ovs_version: "2.16.4"

```

## Snap

To get the config options for a snap:

```
sudo snap get -d microstack
{
        "compute": {
                "node": {}
        },
        "control-plane": {
                "cloud": "microk8s",
                "model": "openstack"
        },
        "microk8s": {
                "dns": "8.8.8.8,8.8.4.4",
                "metallb": "10.20.20.1/29"
        },
        "node": {
                "role": "CONVERGED"
        },
        "snap": {
                "channel": {
                        "juju": "3.0/stable",
                        "microk8s": "1.25-strict/stable",
                        "openstack-hypervisor": "xena/edge"
                }
        }
}
```

Running command within snap

```
sudo snap run --shell openstack-hypervisor.neutron-ovn-metadata-agent

```

See a snaps connections

```
sudo snap connections microstack          
```
