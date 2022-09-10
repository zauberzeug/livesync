FROM alpine

RUN apk add --no-cache rsync openssh

RUN ssh-keygen -A

WORKDIR /root

EXPOSE 22

CMD while true; do /usr/sbin/sshd -d -D; sleep 0.2; done