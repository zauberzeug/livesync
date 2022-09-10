FROM alpine

RUN apk add --no-cache rsync openssh

RUN ssh-keygen -A

WORKDIR /root

EXPOSE 22

ENTRYPOINT chmod 700 /root/.ssh; chmod 600 /root/.ssh/authorized_keys # because we mount the volume as root

CMD while true; do /usr/sbin/sshd -d -D; sleep 0.2; done