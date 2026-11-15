# 開発・保守担当者向け

社員の操作説明は[社員向け](USER_GUIDE.md)、設置・運用は[サーバー担当者向け](SERVER_GUIDE.md)を参照してください。

## 技術資料

- [設計書](../ARCHITECTURE.md)：構成と要件
- [設計レビュー](../DESIGN_REVIEW.md)：指摘と判断の経緯
- [検証状況](../VALIDATION.md)：実施したテストと残課題

React・TypeScript・Viteの画面、DjangoのAPI、Channels・Redisの通知、PostgreSQLの永続化で構成しています。frontend/が画面、backend/がサーバー、infra/が運用・配布スクリプトです。

## ソースからの起動

.env.exampleから.envを作成し、SECRET_KEYとPOSTGRES_PASSWORDへランダム値を設定します。

    docker compose up -d --build
    docker compose exec app python manage.py bootstrap

標準はlocalhost:8080限定。新規環境のみbootstrapを使用します。初期化済みの開発PCの情報は.local/初回ログイン.txtにあります。試験投稿は「動作確認」チャンネルに残り、試験アカウントは無効化済みです。

## ビルド・検証

バックエンド:

    docker compose run --rm app python manage.py test chat

フロントエンド（frontendフォルダで実行）:

    npm ci
    npm run build

Python依存はbackend/requirements.lock、フロント依存はfrontend/package-lock.jsonで固定しています。イメージはリリースごとに識別し、依存更新時は認証・権限・再接続・バックアップ復元も検証します。

## 配布物を作る

ビルド済みイメージを用意した上で実行します。

Linux:

    bash infra/export.sh

PowerShell:

    ./infra/export.ps1

dist-release/に全サービスイメージ、Compose設定、運用スクリプト、利用ガイドと技術資料をまとめます。秘密情報・証明書・DB・添付は含めません。ホスト間のデータ移設は[運用手順](SERVER_GUIDE.md)を使用してください。

文書を変更した場合も配布物側へ反映します。READMEだけをコピーするとガイドへのリンクが切れるため、docs/と参照先の技術資料を一緒に配布してください。

## 保守時に確認する仕様

会話・添付・検索・WebSocketすべてでアクセス権を検証します。投稿の重複排除と順序、スレッド未読、通知欠落時の再同期を維持してください。設計時点の要件と実装の差は、検証状況と各利用ガイドへ明記します。

[入口へ戻る](../README.md)
