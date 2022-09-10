FROM alpine

RUN apk add --no-cache rsync openssh

RUN ssh-keygen -A

WORKDIR /root

EXPOSE 22

CMD chown -R root:root /root; chmod 700 /root/.ssh; chmod 600 /root/.ssh/authorized_keys; ls -lha /root/.ssh; /usr/sbin/sshd -D -d