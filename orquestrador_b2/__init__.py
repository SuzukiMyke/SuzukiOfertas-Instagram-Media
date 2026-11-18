"""Orquestrador B2 (GOAL 5.14-B2): ficha de curadoria FICTÍCIA -> exportação B (1.1) -> receptor -> fundo de marca -> carrossel renderizado.

Reutiliza, sem alterá-los: ``curadoria_b`` (exportador), ``produtos`` (receptor 1.1 e ponte ``ficha_para_carrossel_v11``) e ``gerador``
(``Catalogo``, ``fundo_marca.registrar``, ``carrossel.gerar``). Só produtos fictícios; sem rede, sem publicação, sem agendamento.
As saídas ficam FORA do repositório (o fluxo recusa uma pasta de saída dentro dele) e nada é versionado.
"""
