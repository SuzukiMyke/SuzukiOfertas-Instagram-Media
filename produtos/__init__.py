"""Integração de produtos (Etapa 5.8): leitor, validador e fichas — lado Instagram.

Implementa o contrato JSON v1 (``CONTRATO_PRODUTOS_INSTAGRAM.md``, repositório de
documentação) somente do lado do Instagram. Biblioteca padrão apenas; **sem rede**,
sem acesso ao agente de ofertas, a bancos, cofres ou credenciais.

Fluxo: pasta de troca (somente leitura) -> ``leitor`` -> ``esquema`` (validação) ->
``registro`` (deduplicação/histórico/arquivamento) -> ``avaliacao`` (expiração e estados,
com decisões humanas de ``decisoes``) -> ``fichas`` (JSON + Markdown) ->
``reel_fragmento`` (conversão opcional, sem executar o gerador de Reels).
"""
FICHA_VERSION = "1.0.0"
