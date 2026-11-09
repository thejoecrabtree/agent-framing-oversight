// Turn judge classes into oversight scores with the study's own verdict code (approval-judge-study/src/judges.mjs,
// imported read-only): the gateway's judge() at the post-#15 commit, scored block 4 / ask 3 / ask+default 2 /
// recall 1 / do 0, drop.marketing 4.
//   node src/scores.mjs < rows.jsonl > scores.jsonl      rows: {key, card:{id,agent,kind,channel,standing,title,body}, classes:[...]}
import fs from "node:fs";
import { verdicts, SCORE } from "../../src/judges.mjs";

for (const line of fs.readFileSync(0, "utf8").split("\n").filter(Boolean)) {
  const r = JSON.parse(line);
  const llm = Object.fromEntries(r.classes.map((c, i) => [`j${i}`, { [r.card.id]: c }]));
  const vs = verdicts(r.card, llm);
  const scores = r.classes.map((_, i) => (vs[`j${i}`].verdict === "missing" ? null : SCORE(vs[`j${i}`])));
  process.stdout.write(JSON.stringify({ key: r.key, scores }) + "\n");
}
