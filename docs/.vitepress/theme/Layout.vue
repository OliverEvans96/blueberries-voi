<script setup lang="ts">
import DefaultTheme from "vitepress/theme";
import { withBase } from "vitepress";

const { Layout } = DefaultTheme;
</script>

<template>
  <Layout>
    <template #nav-bar-title-before>
      <a class="nav-brand" :href="withBase('/')">
        <span class="nav-brand-title">Blueberries VOI</span>
        <span class="nav-brand-chip">AI-generated docs</span>
      </a>
    </template>
  </Layout>
</template>
