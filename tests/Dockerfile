FROM alpine

RUN apk add --no-cache rsync openssh

# Modify the sshd_config to change the port
RUN echo "Port 2222" >> /etc/ssh/sshd_config

RUN ssh-keygen -A

WORKDIR /root

EXPOSE 2222

CMD chown -R root:root /root; chmod 700 /root/.ssh; chmod 600 /root/.ssh/authorized_keys; ls -lha /root/.ssh; /usr/sbin/sshd -D