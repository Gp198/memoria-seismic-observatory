# MEMÓRIA v0.6.2 — Assistant light-theme contrast hotfix

## Problem

The MEMÓRIA sidebar has a permanent dark background. A broad CSS rule made all
sidebar descendants white. Streamlit light mode renders text areas, select boxes
and secondary buttons with white surfaces, producing white text on white
backgrounds in the assistant panel.

## Fix

The application now assigns explicit, theme-independent colours to sidebar form
controls:

- dark text and caret on white input, textarea and select surfaces;
- visible placeholder and disabled-control text;
- dark text on secondary buttons;
- white text on primary buttons;
- readable dropdown options rendered through BaseWeb portals;
- focus borders with sufficient contrast.

Normal sidebar copy and assistant responses remain white on the dark sidebar.
The patch changes presentation only and does not affect the Mistral integration,
scientific calculations, data layers or pipelines.
