import type { ProjectStructure } from "@/types/api";

type StoryBibleSaveTargetFieldProps = {
  structure: ProjectStructure | null;
  branchId: string | null;
  onChange: (branchId: string) => void;
  disabled?: boolean;
};

export function StoryBibleSaveTargetField({
  structure,
  branchId,
  onChange,
  disabled = false,
}: StoryBibleSaveTargetFieldProps) {
  const branches = structure?.branches ?? [];
  const placeholderLabel = structure ? "请选择分支" : "加载分支中...";

  return (
    <div className="md:col-span-2">
      <label className="block text-sm font-medium text-black/70">保存目标分支</label>
      <select
        value={branchId ?? ""}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled || branches.length === 0}
        className="mt-2 w-full rounded-xl border border-black/10 bg-white px-4 py-2 disabled:bg-black/5"
      >
        <option value="" disabled>
          {placeholderLabel}
        </option>
        {branches.map((branch) => (
          <option key={branch.id} value={branch.id}>
            {branch.title}
            {branch.is_default ? " · 默认" : ""}
          </option>
        ))}
      </select>
      <p className="mt-2 text-xs leading-6 text-black/45">
        {branches.length > 0
          ? "保存时会写入所选分支的 Story Bible 快照。"
          : "当前项目还没有可用分支，暂时无法保存到 Story Bible。"}
      </p>
    </div>
  );
}
