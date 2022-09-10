FROM alpine

RUN apk add --no-cache rsync openssh

RUN ssh-keygen -A

WORKDIR /root

EXPOSE 22

CMD ["/usr/sbin/sshd", "-d", "-D"]