"use client";

import { CodeEditor } from "./code-editor";
import { CopyButton } from "./copy-button";

type ProblemSample = {
  input: string;
  output: string;
};

type ProblemSpec = {
  title: string;
  statement: string;
  input_format: string;
  output_format: string;
  constraints: Record<string, string>;
  samples: ProblemSample[];
  problem_type_guess: string[];
  special_notes: string[];
  parse_confidence: Record<string, number>;
};

type ProblemSpecEditorProps = {
  value: ProblemSpec;
  busy: boolean;
  disabled: boolean;
  onChange: (nextValue: ProblemSpec) => void;
  onSave: () => void;
  onReset: () => void;
};

export function ProblemSpecEditor({
  value,
  busy,
  disabled,
  onChange,
  onSave,
  onReset,
}: ProblemSpecEditorProps) {
  const constraintEntries = Object.entries(value.constraints);
  const confidenceEntries = Object.entries(value.parse_confidence);

  function patch(next: Partial<ProblemSpec>) {
    onChange({ ...value, ...next });
  }

  function updateSample(index: number, nextSample: ProblemSample) {
    const nextSamples = value.samples.map((sample, sampleIndex) =>
      sampleIndex === index ? nextSample : sample,
    );
    patch({ samples: nextSamples });
  }

  function addSample() {
    patch({
      samples: [...value.samples, { input: "", output: "" }],
    });
  }

  function removeSample(index: number) {
    patch({
      samples: value.samples.filter((_, sampleIndex) => sampleIndex !== index),
    });
  }

  function updateConstraint(index: number, nextKey: string, nextValue: string) {
    const nextEntries: Array<[string, string]> = constraintEntries.map(
      ([key, currentValue], entryIndex) =>
        entryIndex === index ? [nextKey, nextValue] : [key, currentValue],
    );
    patch({ constraints: toConstraintMap(nextEntries) });
  }

  function addConstraint() {
    patch({
      constraints: {
        ...value.constraints,
        [`constraint_${constraintEntries.length + 1}`]: "",
      },
    });
  }

  function removeConstraint(index: number) {
    patch({
      constraints: toConstraintMap(
        constraintEntries.filter((_, entryIndex) => entryIndex !== index),
      ),
    });
  }

  return (
    <div className="stack">
      <div className="metaRow">
        <CopyButton text={JSON.stringify(value, null, 2)} label="复制 Spec JSON" />
        <button
          type="button"
          className="button secondary buttonSmall"
          onClick={onReset}
          disabled={busy || disabled}
        >
          重置
        </button>
        <button
          type="button"
          className="button buttonSmall"
          onClick={onSave}
          disabled={busy || disabled}
        >
          保存 Spec
        </button>
      </div>

      <div className="formGrid">
        <label className="field">
          <span className="fieldLabel">标题</span>
          <input
            className="input"
            value={value.title}
            disabled={disabled}
            onChange={(event) => patch({ title: event.target.value })}
          />
        </label>

        <label className="field">
          <span className="fieldLabel">题型猜测</span>
          <textarea
            className="textarea textareaCompact"
            value={value.problem_type_guess.join("\n")}
            disabled={disabled}
            onChange={(event) => patch({ problem_type_guess: splitLines(event.target.value) })}
          />
        </label>
      </div>

      <label className="field">
        <span className="fieldLabel">题目描述</span>
        <textarea
          className="textarea"
          value={value.statement}
          disabled={disabled}
          onChange={(event) => patch({ statement: event.target.value })}
        />
      </label>

      <div className="formGrid">
        <label className="field">
          <span className="fieldLabel">输入格式</span>
          <textarea
            className="textarea"
            value={value.input_format}
            disabled={disabled}
            onChange={(event) => patch({ input_format: event.target.value })}
          />
        </label>

        <label className="field">
          <span className="fieldLabel">输出格式</span>
          <textarea
            className="textarea"
            value={value.output_format}
            disabled={disabled}
            onChange={(event) => patch({ output_format: event.target.value })}
          />
        </label>
      </div>

      <section className="stack subtleCard">
        <div className="sectionHeader">
          <h3>约束</h3>
          <button
            type="button"
            className="button secondary buttonSmall"
            onClick={addConstraint}
            disabled={busy || disabled}
          >
            添加约束
          </button>
        </div>

        {constraintEntries.length > 0 ? (
          <div className="stack">
            {constraintEntries.map(([constraintKey, constraintValue], index) => (
              <div key={`${constraintKey}-${index}`} className="kvRow">
                <input
                  className="input"
                  value={constraintKey}
                  disabled={disabled}
                  onChange={(event) =>
                    updateConstraint(index, event.target.value, constraintValue)
                  }
                  placeholder="约束名"
                />
                <input
                  className="input"
                  value={constraintValue}
                  disabled={disabled}
                  onChange={(event) =>
                    updateConstraint(index, constraintKey, event.target.value)
                  }
                  placeholder="约束值"
                />
                <button
                  type="button"
                  className="button ghost buttonSmall"
                  onClick={() => removeConstraint(index)}
                  disabled={busy || disabled}
                >
                  删除
                </button>
              </div>
            ))}
          </div>
        ) : (
          <div className="emptyState">当前没有约束。</div>
        )}
      </section>

      <section className="stack subtleCard">
        <div className="sectionHeader">
          <h3>样例</h3>
          <button
            type="button"
            className="button secondary buttonSmall"
            onClick={addSample}
            disabled={busy || disabled}
          >
            添加样例
          </button>
        </div>

        {value.samples.length > 0 ? (
          <div className="stack">
            {value.samples.map((sample, index) => (
              <div key={`sample-${index}`} className="sampleCard">
                <div className="metaRow">
                  <div className="pill">样例 {index + 1}</div>
                  <button
                    type="button"
                    className="button ghost buttonSmall"
                    onClick={() => removeSample(index)}
                    disabled={busy || disabled}
                  >
                    删除
                  </button>
                </div>
                <div className="formGrid">
                  <label className="field">
                    <span className="fieldLabel">输入</span>
                    <textarea
                      className="textarea"
                      value={sample.input}
                      disabled={disabled}
                      onChange={(event) =>
                        updateSample(index, { ...sample, input: event.target.value })
                      }
                    />
                  </label>
                  <label className="field">
                    <span className="fieldLabel">输出</span>
                    <textarea
                      className="textarea"
                      value={sample.output}
                      disabled={disabled}
                      onChange={(event) =>
                        updateSample(index, { ...sample, output: event.target.value })
                      }
                    />
                  </label>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="emptyState">当前没有样例。</div>
        )}
      </section>

      <label className="field">
        <span className="fieldLabel">特殊说明</span>
        <textarea
          className="textarea textareaCompact"
          value={value.special_notes.join("\n")}
          disabled={disabled}
          onChange={(event) => patch({ special_notes: splitLines(event.target.value) })}
        />
      </label>

      <section className="stack subtleCard">
        <div className="sectionHeader">
          <h3>解析置信度</h3>
          <div className="pill">{confidenceEntries.length} 项</div>
        </div>

        {confidenceEntries.length > 0 ? (
          <div className="runtimeGrid">
            {confidenceEntries.map(([name, score]) => (
              <div key={name} className="infoItem">
                <div className="infoLabel">{name}</div>
                <div className="infoValue">{formatConfidence(score)}</div>
              </div>
            ))}
          </div>
        ) : (
          <div className="emptyState">当前没有解析置信度信息。</div>
        )}
      </section>

      <section className="stack">
        <div className="sectionHeader">
          <h3>Spec JSON 预览</h3>
          <CopyButton text={JSON.stringify(value, null, 2)} label="复制 JSON" />
        </div>
        <CodeEditor
          value={JSON.stringify(value, null, 2)}
          language="json"
          readOnly
          height={260}
        />
      </section>
    </div>
  );
}

function splitLines(value: string): string[] {
  return value
    .split(/\r?\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function toConstraintMap(entries: Array<[string, string]>): Record<string, string> {
  return Object.fromEntries(entries.filter(([key]) => key.trim()));
}

function formatConfidence(value: number): string {
  if (!Number.isFinite(value)) {
    return "-";
  }
  return `${Math.round(value * 100)}%`;
}
