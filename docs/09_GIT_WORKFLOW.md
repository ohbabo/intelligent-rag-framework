# 09. Git Workflow

## 새 프로젝트로 분리하는 경우

```bash
git init intelligent-rag-framework
cd intelligent-rag-framework

# 이 문서 폴더 복사 후
git add .
git commit -m "docs: initialize intelligent rag framework philosophy"
```

## GitHub 원격 연결

```bash
git remote add origin git@github.com:<OWNER>/intelligent-rag-framework.git
git branch -M main
git push -u origin main
```

## Claude 구현 브랜치

```bash
git checkout -b feat/c-core-mvp
```

## 첫 구현 커밋 단위

```text
commit 1: add C core public header
commit 2: add engine/entity/relation storage
commit 3: add observation/claim/evidence structs
commit 4: add rule engine MVP
commit 5: add gap/score/memory gate
commit 6: add Python ctypes wrapper
```

## 커밋 메시지 예시

```text
docs: initialize framework identity
core: add engine lifecycle API
core: add entity and relation storage
core: add rule expansion MVP
core: add score and memory gate
python: add ctypes wrapper for ragcore
```
