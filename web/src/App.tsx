import { StudioLayout } from "./react/StudioLayout";
import { StudioProvider } from "./react/StudioProvider";

export function App() {
  return (
    <StudioProvider>
      <StudioLayout />
    </StudioProvider>
  );
}
