import React from "react";
import { createRoot } from "react-dom/client";
import PasswordGate from "./src/components/PasswordGate.jsx";

const root = createRoot(document.getElementById("root"));
root.render(
  <PasswordGate>
    <div id="secret">secret app content</div>
  </PasswordGate>,
);
