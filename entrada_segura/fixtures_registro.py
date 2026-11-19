"""Registro de fixtures por CONJUNTO aprovado (§4.6): hashes LITERAIS gerados uma vez (script descartável) do commit-base 927f877.

Um lote só tem procedência registrada se o conjunto dos seus arquivos for EXATAMENTE igual (caminhos relativos e SHA-256, nem a mais nem a
menos) a UM conjunto abaixo. Combinação de arquivos reconhecidos individualmente NÃO é lote confiável. Fixtures dinâmicas dos testes não
entram aqui. Alterar uma fixture versionada exige revisar o registro (teste de cobertura exata).
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class ConjuntoFixture:
    id: str
    base: str                      # pasta (ou arquivo) no repositório: só documentação/auditoria
    arquivos: Mapping[str, str]    # caminho relativo ao lote → SHA-256


def _c(id_: str, base: str, arquivos: dict) -> ConjuntoFixture:
    return ConjuntoFixture(id_, base, MappingProxyType(dict(arquivos)))


CONJUNTOS: tuple[ConjuntoFixture, ...] = (
    # produtos/exemplos_ficticios (17 arquivo(s))
    _c("produtos/exemplos_ficticios", "produtos/exemplos_ficticios", {
        "decisoes/decisoes_exemplo.json": "4463de33b92f63be99e372a247dca2e6d9dd771e2959695cf822ca5065562fdb",
        "troca/.oculto_A011.json": "037b01de1c8cf80c02cedf606d22d49e1ef491cd7325ce130cf3e9da2bb472d7",
        "troca/manifest.json": "f1c96e7d3aed1c48a8377fdfcbd8aac1335523b67eeeaabf8313b794203535a4",
        "troca/produto_EXEMPLO_A_A001_20261117T130500Z.json": "f9a64551842b79c395a08c3406b456d8c1a1f21a7c140a0f35cb94fa9bc9b3a7",
        "troca/produto_EXEMPLO_A_A002_20261117T060500Z.json": "f230181640a1393b339d20976fb53cc83eb96007f4754be867dcd23fe77b0385",
        "troca/produto_EXEMPLO_A_A003_20261117T130500Z.json": "b7fa4adf58df6f7178dc819f7591a3da685089ad8078385e87f9f97b5b806b80",
        "troca/produto_EXEMPLO_A_A004_20261117T120000Z.json": "184b38368a9b327c94be2995cfeea25727f189e8ed672a9e36d45269d564a1f7",
        "troca/produto_EXEMPLO_A_A004_20261117T140000Z.json": "89ac5125e386fff5b266e5d8a739037a7927b70c9c63b1a325d7d81cad8c82cf",
        "troca/produto_EXEMPLO_A_A005_20261117T130500Z.json": "a64e322dcdcd1947205c9e2474809da0288bfe5cb0293229d775602c42d148a3",
        "troca/produto_EXEMPLO_A_A006_20261117T130500Z.json": "8b84b7beefc49acc20e09878b73c1659d197c5e1187b29a64ca7d9044e857c39",
        "troca/produto_EXEMPLO_A_A007_20261117T140000Z.json.tmp": "aa76ab70c21b8ee431bb760c1fa06766a4ba4aad60c2e7d8d8361073c9f4ad05",
        "troca/produto_EXEMPLO_A_A008_20261117T130500Z.json": "1b3ad5a0ca458dad084f57dc8d2a6c4df552ea6c85abce5bfe5cfb7d4657fbbd",
        "troca/produto_EXEMPLO_A_A009_20261117T130500Z.json": "0336c016886590bf3e16970fe51b88ef336af19e57659c587a4f3956519253da",
        "troca/produto_EXEMPLO_A_A010_20261117T130500Z.json": "a6f0a13366c9bd6bcce9c1c8b641c6491fbeb580a6ec5c3d0fa67fc6d0d63681",
        "troca/produto_EXEMPLO_B_B001_20261117T120000Z.json": "77fc12c8c2b02b2515666ba69cb98e7e1438756b572fff24fd6af6f1ecb7f0e1",
        "troca/produto_EXEMPLO_B_B002_20261117T120000Z.json": "1fa3b243bb4a92e6b0880b0b811b49820603d856207124b242bd419ded9a34d3",
        "troca/produto_EXEMPLO_B_B003_20261117T120000Z.json": "fcf0884b95819dabd1aabf896c0e806773a814db994cdc3ffe83e7548f816e58",
    }),
    # produtos/exemplos_ficticios/troca (16 arquivo(s))
    _c("produtos/exemplos_ficticios/troca", "produtos/exemplos_ficticios/troca", {
        ".oculto_A011.json": "037b01de1c8cf80c02cedf606d22d49e1ef491cd7325ce130cf3e9da2bb472d7",
        "manifest.json": "f1c96e7d3aed1c48a8377fdfcbd8aac1335523b67eeeaabf8313b794203535a4",
        "produto_EXEMPLO_A_A001_20261117T130500Z.json": "f9a64551842b79c395a08c3406b456d8c1a1f21a7c140a0f35cb94fa9bc9b3a7",
        "produto_EXEMPLO_A_A002_20261117T060500Z.json": "f230181640a1393b339d20976fb53cc83eb96007f4754be867dcd23fe77b0385",
        "produto_EXEMPLO_A_A003_20261117T130500Z.json": "b7fa4adf58df6f7178dc819f7591a3da685089ad8078385e87f9f97b5b806b80",
        "produto_EXEMPLO_A_A004_20261117T120000Z.json": "184b38368a9b327c94be2995cfeea25727f189e8ed672a9e36d45269d564a1f7",
        "produto_EXEMPLO_A_A004_20261117T140000Z.json": "89ac5125e386fff5b266e5d8a739037a7927b70c9c63b1a325d7d81cad8c82cf",
        "produto_EXEMPLO_A_A005_20261117T130500Z.json": "a64e322dcdcd1947205c9e2474809da0288bfe5cb0293229d775602c42d148a3",
        "produto_EXEMPLO_A_A006_20261117T130500Z.json": "8b84b7beefc49acc20e09878b73c1659d197c5e1187b29a64ca7d9044e857c39",
        "produto_EXEMPLO_A_A007_20261117T140000Z.json.tmp": "aa76ab70c21b8ee431bb760c1fa06766a4ba4aad60c2e7d8d8361073c9f4ad05",
        "produto_EXEMPLO_A_A008_20261117T130500Z.json": "1b3ad5a0ca458dad084f57dc8d2a6c4df552ea6c85abce5bfe5cfb7d4657fbbd",
        "produto_EXEMPLO_A_A009_20261117T130500Z.json": "0336c016886590bf3e16970fe51b88ef336af19e57659c587a4f3956519253da",
        "produto_EXEMPLO_A_A010_20261117T130500Z.json": "a6f0a13366c9bd6bcce9c1c8b641c6491fbeb580a6ec5c3d0fa67fc6d0d63681",
        "produto_EXEMPLO_B_B001_20261117T120000Z.json": "77fc12c8c2b02b2515666ba69cb98e7e1438756b572fff24fd6af6f1ecb7f0e1",
        "produto_EXEMPLO_B_B002_20261117T120000Z.json": "1fa3b243bb4a92e6b0880b0b811b49820603d856207124b242bd419ded9a34d3",
        "produto_EXEMPLO_B_B003_20261117T120000Z.json": "fcf0884b95819dabd1aabf896c0e806773a814db994cdc3ffe83e7548f816e58",
    }),
    # produtos/exemplos_ficticios/decisoes (1 arquivo(s))
    _c("produtos/exemplos_ficticios/decisoes", "produtos/exemplos_ficticios/decisoes", {
        "decisoes_exemplo.json": "4463de33b92f63be99e372a247dca2e6d9dd771e2959695cf822ca5065562fdb",
    }),
    # produtos/exemplos_ficticios_v1_1 (11 arquivo(s))
    _c("produtos/exemplos_ficticios_v1_1", "produtos/exemplos_ficticios_v1_1", {
        "README.md": "c03822152424e1ae0773c073e1113ecad6432e7489556dde441f5b84f66a0388",
        "decisoes/decisoes.json": "81099096b6059b0cb90045a54657fe12d41a79da9ad9758b89fe997a845c497d",
        "decisoes/permissoes_fotos.json": "e76d6047e692b1e1c7a5f3a6567ad4c6a6d4c3d89e075b9d176b5e37f9c5af27",
        "decisoes/termos_programas.json": "9bebd680af4ecf7882829f8e72a2ddb7f9ee97d4d075d839cf641abf2103e832",
        "exportacoes/A/manifest.json": "0039a592163ad3ff091636877efbc0dc72ea7dada2cf3d9774e5fb63c6655352",
        "exportacoes/A/produto_EXEMPLO_A_A001_20261117T130500Z.json": "f9a64551842b79c395a08c3406b456d8c1a1f21a7c140a0f35cb94fa9bc9b3a7",
        "exportacoes/A/produto_EXEMPLO_A_A002_20261117T130500Z.json": "1c9925ed732aac0607da20c6bc2788d675d90630e930f0a59d77fa09fc68b28f",
        "exportacoes/B/manifest.json": "b6b1cbfd174919de6aced9c930ab927c445a27e9fb73ce65b8623633a28d8045",
        "exportacoes/B/produto_EXEMPLO_B_B001_20261117T120000Z.json": "9c1c6d394b599236ba7b76acd92a2f3d982b36265e9943f5b59faf99a7cb42d7",
        "fotos/evidencias/termo_ficticio_001.txt": "0288c1c8c62c54a10caa50cf8feed8c9b516961531c026244a0c21a43b07c0b9",
        "fotos/fotos/2e574a430ab2b13cbe5021ad8ee547080a3abf42249e0a68ed7f36f29d8ead28.jpg": "2e574a430ab2b13cbe5021ad8ee547080a3abf42249e0a68ed7f36f29d8ead28",
    }),
    # produtos/exemplos_ficticios_v1_1/exportacoes (5 arquivo(s))
    _c("produtos/exemplos_ficticios_v1_1/exportacoes", "produtos/exemplos_ficticios_v1_1/exportacoes", {
        "A/manifest.json": "0039a592163ad3ff091636877efbc0dc72ea7dada2cf3d9774e5fb63c6655352",
        "A/produto_EXEMPLO_A_A001_20261117T130500Z.json": "f9a64551842b79c395a08c3406b456d8c1a1f21a7c140a0f35cb94fa9bc9b3a7",
        "A/produto_EXEMPLO_A_A002_20261117T130500Z.json": "1c9925ed732aac0607da20c6bc2788d675d90630e930f0a59d77fa09fc68b28f",
        "B/manifest.json": "b6b1cbfd174919de6aced9c930ab927c445a27e9fb73ce65b8623633a28d8045",
        "B/produto_EXEMPLO_B_B001_20261117T120000Z.json": "9c1c6d394b599236ba7b76acd92a2f3d982b36265e9943f5b59faf99a7cb42d7",
    }),
    # produtos/exemplos_ficticios_v1_1/exportacoes/A (3 arquivo(s))
    _c("produtos/exemplos_ficticios_v1_1/exportacoes/A", "produtos/exemplos_ficticios_v1_1/exportacoes/A", {
        "manifest.json": "0039a592163ad3ff091636877efbc0dc72ea7dada2cf3d9774e5fb63c6655352",
        "produto_EXEMPLO_A_A001_20261117T130500Z.json": "f9a64551842b79c395a08c3406b456d8c1a1f21a7c140a0f35cb94fa9bc9b3a7",
        "produto_EXEMPLO_A_A002_20261117T130500Z.json": "1c9925ed732aac0607da20c6bc2788d675d90630e930f0a59d77fa09fc68b28f",
    }),
    # produtos/exemplos_ficticios_v1_1/exportacoes/B (2 arquivo(s))
    _c("produtos/exemplos_ficticios_v1_1/exportacoes/B", "produtos/exemplos_ficticios_v1_1/exportacoes/B", {
        "manifest.json": "b6b1cbfd174919de6aced9c930ab927c445a27e9fb73ce65b8623633a28d8045",
        "produto_EXEMPLO_B_B001_20261117T120000Z.json": "9c1c6d394b599236ba7b76acd92a2f3d982b36265e9943f5b59faf99a7cb42d7",
    }),
    # produtos/exemplos_ficticios_v1_1/decisoes (3 arquivo(s))
    _c("produtos/exemplos_ficticios_v1_1/decisoes", "produtos/exemplos_ficticios_v1_1/decisoes", {
        "decisoes.json": "81099096b6059b0cb90045a54657fe12d41a79da9ad9758b89fe997a845c497d",
        "permissoes_fotos.json": "e76d6047e692b1e1c7a5f3a6567ad4c6a6d4c3d89e075b9d176b5e37f9c5af27",
        "termos_programas.json": "9bebd680af4ecf7882829f8e72a2ddb7f9ee97d4d075d839cf641abf2103e832",
    }),
    # produtos/exemplos_ficticios_v1_1/fotos (2 arquivo(s))
    _c("produtos/exemplos_ficticios_v1_1/fotos", "produtos/exemplos_ficticios_v1_1/fotos", {
        "evidencias/termo_ficticio_001.txt": "0288c1c8c62c54a10caa50cf8feed8c9b516961531c026244a0c21a43b07c0b9",
        "fotos/2e574a430ab2b13cbe5021ad8ee547080a3abf42249e0a68ed7f36f29d8ead28.jpg": "2e574a430ab2b13cbe5021ad8ee547080a3abf42249e0a68ed7f36f29d8ead28",
    }),
    # curadoria_b/exemplos_ficticios (1 arquivo(s))
    _c("curadoria_b/exemplos_ficticios", "curadoria_b/exemplos_ficticios", {
        "ficha_valida.json": "68e4dd96bee57e61ddd1e5670153c81381de8035156b5766a01e95099af989a3",
    }),
    # orquestrador_b2/exemplos_ficticios (3 arquivo(s))
    _c("orquestrador_b2/exemplos_ficticios", "orquestrador_b2/exemplos_ficticios", {
        "ficha_casa_cozinha_panela.json": "8047e9c5290dea75ce9fcee5473a88d9dc0eca21fc87e62648f5c9a4eee68fff",
        "ficha_ferramentas_furadeira.json": "8de1ee5e173ef3a23d98ec2a40fb1ad6e6ed3abbdec2aa0f8d2d4e024159f545",
        "ficha_tecnologia_fone.json": "4497a653c3bf56b699d6d3fddcfa259e33ca38da42eeda5af4dd37d2905166c9",
    }),
    # orquestrador_b2/exemplos_ficticios/ficha_tecnologia_fone.json (1 arquivo(s))
    _c("orquestrador_b2/exemplos_ficticios/ficha_tecnologia_fone.json", "orquestrador_b2/exemplos_ficticios/ficha_tecnologia_fone.json", {
        "ficha_tecnologia_fone.json": "4497a653c3bf56b699d6d3fddcfa259e33ca38da42eeda5af4dd37d2905166c9",
    }),
    # orquestrador_b2/exemplos_ficticios/ficha_casa_cozinha_panela.json (1 arquivo(s))
    _c("orquestrador_b2/exemplos_ficticios/ficha_casa_cozinha_panela.json", "orquestrador_b2/exemplos_ficticios/ficha_casa_cozinha_panela.json", {
        "ficha_casa_cozinha_panela.json": "8047e9c5290dea75ce9fcee5473a88d9dc0eca21fc87e62648f5c9a4eee68fff",
    }),
    # orquestrador_b2/exemplos_ficticios/ficha_ferramentas_furadeira.json (1 arquivo(s))
    _c("orquestrador_b2/exemplos_ficticios/ficha_ferramentas_furadeira.json", "orquestrador_b2/exemplos_ficticios/ficha_ferramentas_furadeira.json", {
        "ficha_ferramentas_furadeira.json": "8de1ee5e173ef3a23d98ec2a40fb1ad6e6ed3abbdec2aa0f8d2d4e024159f545",
    }),
    # exemplos (1 arquivo(s))
    _c("exemplos", "exemplos", {
        "carrossel_exemplo.json": "9c86079312d601ae1511dfee1f91adc3acbf6beb2b8522b70b064c827faf0cc1",
    }),
)
