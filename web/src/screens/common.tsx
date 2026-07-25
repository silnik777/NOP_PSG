import { useEffect, useState } from "react";
import { loadProfiles, RefProfile } from "../api";
import { Sel } from "../ui";

/** Composition source shared by module screens: reference profile code. */
export function useProfiles(): RefProfile[] {
  const [profiles, setProfiles] = useState<RefProfile[]>([]);
  useEffect(() => {
    loadProfiles().then(setProfiles).catch(() => setProfiles([]));
  }, []);
  return profiles;
}

export function ProfilePicker({
  value, onChange, profiles, label = "Profil gazu (referencyjny)",
}: {
  value: string;
  onChange: (v: string) => void;
  profiles: RefProfile[];
  label?: string;
}) {
  const options: [string, string][] = profiles.length
    ? profiles.map((p) => [p.code, `${p.code} — ${p.name}`])
    : [[value, value]];
  return <Sel label={label} value={value} onChange={onChange} options={options} />;
}
