# NaChat

社内LAN向けのチャット初期実装。React + Django + PostgreSQL + Redis。Docker Composeで動作します。

## このPCで試す

起動済みなら http://localhost:8080 を開きます。初回ログイン情報は `.local/初回ログイン.txt` に保存されます。初回ログインで12文字以上の新しいパスワードに変更してください。このファイルは変更後に削除できます。

```powershell
docker compose up -d
docker compose stop
```

初期設定はlocalhost限定です。DBとRedisのポートはホストに公開していません。

## 新しい環境をソースから構築

1. Docker Engine（Windows開発ではDocker Desktop）とComposeを用意。
2. `.env.example` を `.env` にコピー。SECRET_KEYとPOSTGRES_PASSWORDをそれぞれランダムな値に変更。
3. `docker compose up -d --build` を実行。DB準備完了→マイグレーション→アプリ→Web配信の順で起動。
4. `docker compose exec app python manage.py bootstrap` で最初の管理者を作成。
5. ブラウザでログインし、設定→ユーザー管理からメンバーを追加。

更新時はバックアップ後にビルドし、`docker compose up -d`。DB変更に非互換がある場合はイメージだけを戻さず、バックアップを別環境に復元します。

## Linuxホストへ持ち運ぶ

PythonやNode.jsをホストに追加する必要はありません。初期対象はlinux/amd64です。

ネット接続可能なビルド環境で `bash infra/export.sh` を実行すると、アプリ・Web・PostgreSQL・Redisの全イメージと起動設定を `dist-release/` にまとめます。Windowsでは同スクリプトのdocker image saveコマンドもPowerShellで実行できます。

持込先では `docker load -i images.tar` で読み込み、環境固有の `.env` を作成して `docker compose up -d --no-build --pull never` を実行します。既存の会話や添付を移す場合は別途バックアップを復元します。イメージに秘密情報とユーザーデータは含めません。

## 社内LAN公開（HTTPS）

1. 社内DNSにホスト名を登録し、クライアントが信頼する証明書を用意。
2. `certs/server.crt` と `certs/server.key` を配置。秘密鍵の読み取り権限を制限。
3. `.env` の `ALLOWED_HOSTS` に社内ホスト名を追加（localhostはヘルスチェック用に残す）。`ORIGINS=https://社内ホスト名`、`SECURE_COOKIES=1` に設定。
4. `docker compose -f compose.yaml -f compose.lan.yaml up -d --no-build --pull never`
5. ホストのファイアウォールで443を社内LANからのみ許可。スリープを無効にし、Dockerの自動起動を設定。

証明書や社内ネットワークが未設定の状態で公開しないでください。LAN用ComposeはlocalhostのHTTPポートを置き換えます。TLS設定自体の現地検証は未実施です。

## 実装した機能

- メール・パスワード認証、初回変更、ログアウト、パスワード変更
- 管理者によるユーザー作成・無効化・再設定
- 公開／非公開チャンネル、チャンネル作成者によるメンバー管理、1対1DM
- 投稿・編集・削除、スレッド、いいね、未読、メールアドレス形式のメンション挿入・強調表示
- 添付（1投稿5個・合計25MB）、権限付きダウンロードと画像プレビュー
- 閲覧可能な会話だけを対象とする検索（最大50件）
- WebSocket更新、15秒ごとの変更照合、重複送信防止、会話単位の連番

「自分へのメンション」はメールアドレスへの言及を検索する一覧です。OS通知、在席・入力中表示、通話は未実装。検索結果は最大50件。会話・スレッド履歴は50件ずつページ表示します。50〜80人の実運用前に、社内条件で容量・負荷・復元時間を確認してください。

このPCの初期環境には「動作確認」チャンネルと試験投稿を残しています。画面試験用アカウントは検証後に無効化しました。通常利用には `.local/初回ログイン.txt` の管理者を使用してください。

## 初期実装のポリシー

- 管理者でも、未参加の非公開会話・DMをアプリ経由では閲覧できません。DBを直接管理できるホスト運用者は別です。
- 追加された非公開メンバーは過去の全履歴を閲覧できます。削除されたメンバーは以後アクセス不可。
- メッセージ削除は行を残し本文を消します。添付は削除投稿からアクセス不可ですが保存領域に残ります。バックアップ内の過去データも残ります。
- ユーザー管理・パスワード変更・メンバー操作をAuditテーブルに記録。本文の編集前履歴は保存しません。
- メッセージ変更記録は現時点では清掃せず保持。添付や監査の保存期間、清掃、RTO/RPOは本番導入前に決定してください。

## バックアップ・復元

Linuxでは `bash infra/backup.sh`。書き込み停止中にDBと添付を揃えて取得し、終了後にアプリを再開します。`backups/日時/` を別ホストに複製してください。`.env`・証明書・鍵は別途安全に保管します。

Windowsでは `./infra/backup.ps1`、持ち運び用イメージの書き出しは `./infra/export.ps1` を使用できます。

復元は空の別Composeプロジェクトに限定します。

```bash
COMPOSE_PROJECT_NAME=nachat-restore bash infra/restore.sh /absolute/path/to/backup
```

復元後は別ポートを割り当てて起動し、履歴・添付・権限を確認してから切り替えます。`docker compose down -v` はデータを削除するため通常の停止には使いません。LAN構成の再開はLAN用Composeを指定してください。

## 管理者パスワード復旧

```text
docker compose exec app python manage.py changepassword 管理者のメール
```

ホスト管理権限を持つ運用者のみ実行します。既存セッションはパスワード変更により失効し、WebSocketも再検証時に切断されます。

## 検証

```text
docker compose run --rm app python manage.py test chat
cd frontend
npm ci
npm run build
```

バージョンはPythonのrequirements.lockとnpmのpackage-lock.jsonで固定。実装に合わせた設計差分はこのREADMEとVALIDATION.mdに記録します。
