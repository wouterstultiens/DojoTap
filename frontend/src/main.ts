import { createApp } from "vue";
import App from "./App.vue";
import { initDiagnostics, logPoint, startTimer } from "./diagnostics";
import "./styles/main.css";

const finishBootstrap = startTimer("app.main.bootstrap");
initDiagnostics();

const app = createApp(App);
logPoint("app.main.createApp");
app.mount("#app");

finishBootstrap();
logPoint("app.main.mounted");
