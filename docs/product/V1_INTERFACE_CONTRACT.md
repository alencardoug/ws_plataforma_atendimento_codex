# V1 Interface Contract

Functional UI only; visual commercialization is V2.

## Customer surface

Required:

- start conversation button/state;
- status indicator: waiting / in service / closed (do not show future ETA);
- scrollable message history;
- text composer/send;
- safe clinical citation cards attached to final operator messages;
- close conversation action.

Never show:

- N1/N2 internal maturity terminology unless later product copy explicitly wants it;
- AI draft;
- retrieval score;
- internal administrative source;
- operator audit data;
- model/provider metadata.

## Operator surface

Desktop functional layout:

```text
+----------------------+---------------------------+--------------------------+
| Queue / Conversations| Selected conversation     | AI / Evidence            |
| waiting + own active | message history/composer  | draft/search/sources     |
+----------------------+---------------------------+--------------------------+
```

### Left pane

- waiting count/list;
- active conversations (max 4);
- unread/last-message indicator;
- claim/release/close controls where valid.

### Center

- customer/operator message history;
- effective mode badge N1/N2;
- manual composer/send always available for assigned active conversation;
- `Take over` visible when effective N2;
- after take-over, badge N1 and no N2 generation control.

### Right pane

N1:

- if assistive search enabled: query/search evidence;
- otherwise disabled/hidden with explanatory state.

N2:

- generate draft for latest eligible customer message;
- display `ANSWER` or `ABSTAIN`;
- `Use suggestion` copies draft into final composer or equivalent controlled flow;
- edit final text;
- regenerate;
- search knowledge;
- evidence cards with type/source/section/score/internal visibility;
- exposable clinical evidence used by the draft is preselected as citation candidates, but operator can remove candidates before send;
- server remains final authority on whether a citation can be exposed.

## No V1 streaming

Customer messages, drafts, and final replies appear as completed payloads. UI may poll or refetch on a short interval; WebSocket/SSE is not required.
