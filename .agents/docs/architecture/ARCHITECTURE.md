# Arquitetura Técnica do Sistema 🏛️

> **Localização Mandatória:** `.agents/docs/architecture/ARCHITECTURE.md`  
> **Responsável:** Arquiteto (`architect.md`)  
> **Última Atualização:** Kickoff / `/init`

---

## 1. Visão Geral da Arquitetura
[Definição de alto nível do sistema, objetivos de escala, disponibilidade e latência.]

---

## 2. Stack Tecnológica Oficial
- **Linguagem Principal (Backend):** [Ex: Python 3.12 / Java 21 / Node.js 20]
- **Framework de Backend:** [Ex: FastAPI / Spring Boot / NestJS]
- **Frontend Web:** [Ex: Angular 18 com SCSS / React com Vite]
- **Camada de Inteligência Artificial / ML:** [Ex: Google GenAI (Gemini), PyTorch, Scikit-Learn, ChromaDB, HuggingFace]
- **Banco de Dados Relacional / NoSQL:** [Ex: PostgreSQL 16 / Firestore Native]
- **Nuvem & Orquestração:** [Ex: Google Cloud Platform (Cloud Run, GCS, Cloud Scheduler)]
- **Ferramentas de Qualidade & CI/CD:** [Ex: Pytest, Flake8/Black, GitHub Actions]

---

## 3. Padrões de Projeto e Estrutura de Diretórios
- **Padrão Arquitetural:** [Ex: Clean Architecture / Hexagonal / Modular Monolith]
- **Separação Rígida de Camadas:**
  - `training_scripts/`: Laboratório offline de experimentação de ML (não vai para produção).
  - `app/ml/` ou `services/`: Inferência online, modelos congelados e regras de serviço.
  - `routers/` ou `controllers/`: Somente roteamento HTTP, validação de schemas e retorno do envelope.
  - `repositories/`: Acesso estrito a dados e banco.

---

## 4. Comunicação e Integrações
- **REST APIs:** Documentadas em `.agents/docs/api_contracts/`.
- **Governança de Erros e Logs:** Estruturados em JSON seguindo `.agents/rules/architecture-error-handling-rules.md`.
