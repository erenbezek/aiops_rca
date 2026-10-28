# Ağ hatası yardımcı imajı (vaka üretimi V2; DECISIONS 2026-10-26 "Ağ hatası aracı"). Yalnız `tc` (iproute2).
# Koşucu bunu hedefin ağ ad alanında (`--network container:<hedef>`), yalnız NET_ADMIN ile, `--rm` olarak çalıştırır:
# netem kuralını koyar ya da siler ve çıkar; kural hedefin ad alanında kalır. Taban ve paket sürümü sabit.
# CI derler, main'de GHCR'a gönderir (.github/workflows/images.yml); koşular digest'le sabit imajı çeker:
# docker pull ghcr.io/erenbezek/aiops-netem@sha256:… (koşucudaki NETEM_IMAGE).
# Yerelde derleme (yalnız deneme için): docker build -t aiops-netem:1 deploy/netem
FROM alpine:3.24.3@sha256:be2656061b536c1883c4034790e21d0a09c5aaaf51968b89368a3c0371ea2c9a
RUN apk add --no-cache iproute2=7.0.0-r0
ENTRYPOINT ["tc"]
