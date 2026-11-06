/**
 * The admin section in plain browser JavaScript: no module, no bundler.
 *
 * The page is complete without this file; the server rendered every banner
 * with the real state. This file adds two things:
 *   1. "Check again": asks GET admin/state, shows the banner of the new
 *      state, replaces versions and time as text and moves the focus to the
 *      state area; a failed request shows the warning banner on top,
 *   2. the test result switch (debug mode only): POST admin/sample on every
 *      change, "Saved" for three seconds, or the error text and the old value.
 *
 * It flips hidden attributes and replaces text, it never builds markup. The
 * request token is read out of the document for every call, because the
 * server rotates it when the session is renewed. Every translated word comes
 * out of a data attribute the template filled.
 */
'use strict'

;(function () {
  const root = document.getElementById('avs-admin')
  const stateArea = document.getElementById('avs-backend-state')
  if (root === null || stateArea === null) {
    return
  }

  const STATES = ['ok', 'version_patch_differs', 'version_drift', 'backend_missing', 'backend_disabled', 'backend_unreachable', 'no_app_api']
  const SAVED_FOR_MS = 3000
  const unknown = root.dataset.unknown || ''

  function url (path) {
    return OC.generateUrl('/apps/audio_video_search/' + path)
  }

  async function ask (path) {
    const response = await fetch(url(path), {
      credentials: 'same-origin',
      headers: {
        requesttoken: document.head.dataset.requesttoken,
        Accept: 'application/json'
      }
    })
    if (!response.ok) {
      throw new Error('audio_video_search: ' + response.status)
    }

    return response.json()
  }

  async function send (path, payload) {
    const response = await fetch(url(path), {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        requesttoken: document.head.dataset.requesttoken,
        'Content-Type': 'application/json',
        Accept: 'application/json'
      },
      body: JSON.stringify(payload)
    })
    if (!response.ok) {
      throw new Error('audio_video_search: ' + response.status)
    }

    return response.json()
  }

  function setText (nodes, value) {
    for (const node of nodes) {
      node.textContent = value
    }
  }

  function version (value) {
    return typeof value === 'string' && value !== '' ? value : unknown
  }

  // The locale of the admin as the server put it on the root element.
  function clock (seconds) {
    const date = new Date(seconds * 1000)
    const locale = (document.documentElement.dataset.locale || document.documentElement.lang || '').replace('_', '-')
    try {
      return date.toLocaleTimeString(locale || undefined)
    } catch (ignored) {
      return date.toLocaleTimeString()
    }
  }

  // -- "Check again" ---------------------------------------------------------

  const button = document.getElementById('avs-recheck')
  const label = document.getElementById('avs-recheck-label')
  const spinner = document.getElementById('avs-recheck-spinner')
  const failed = document.getElementById('avs-recheck-failed')
  const checkedAt = document.getElementById('avs-checked-at')
  const emptyHint = document.getElementById('avs-sample-empty')
  const banners = stateArea.querySelectorAll('[data-state]')
  const idleText = label !== null ? label.textContent : ''

  function busy (on) {
    button.disabled = on
    if (spinner !== null) {
      spinner.hidden = !on
    }
    if (label !== null) {
      label.textContent = on ? (button.dataset.checking || idleText) : idleText
    }
    if (on) {
      stateArea.setAttribute('aria-busy', 'true')
    } else {
      stateArea.removeAttribute('aria-busy')
    }
  }

  function show (answer) {
    for (const banner of banners) {
      banner.hidden = banner.dataset.state !== answer.state
    }
    setText(root.querySelectorAll('.avs-version-own'), version(answer.own))
    setText(root.querySelectorAll('.avs-version-backend'), version(answer.backend))
    if (checkedAt !== null && Number.isInteger(answer.checkedAt)) {
      checkedAt.textContent = clock(answer.checkedAt)
      checkedAt.setAttribute('datetime', new Date(answer.checkedAt * 1000).toISOString())
    }
    if (emptyHint !== null) {
      emptyHint.hidden = Number.isInteger(answer.sampleCount) && answer.sampleCount > 0
    }
  }

  if (button !== null) {
    button.addEventListener('click', async function () {
      busy(true)
      try {
        const answer = await ask('admin/state')
        if (answer === null || typeof answer !== 'object' || !STATES.includes(answer.state)) {
          throw new Error('audio_video_search: unknown state')
        }
        show(answer)
        if (failed !== null) {
          failed.hidden = true
        }
      } catch (error) {
        // The last banner stays; the warning says it is not fresh.
        if (failed !== null) {
          failed.hidden = false
        }
      } finally {
        busy(false)
        stateArea.focus()
      }
    })
  }

  // -- the test result switch (debug mode only) --------------------------------

  const toggle = document.getElementById('avs-sample-visible')
  const status = document.getElementById('avs-sample-status')
  if (toggle === null || status === null) {
    return
  }

  let clearTimer = null

  toggle.addEventListener('change', async function () {
    const wanted = toggle.checked
    toggle.disabled = true
    window.clearTimeout(clearTimer)
    status.textContent = ''
    try {
      const answer = await send('admin/sample', { visible: wanted })
      if (answer === null || answer.visible !== wanted) {
        throw new Error('audio_video_search: switch not stored')
      }
      status.textContent = status.dataset.saved || ''
      clearTimer = window.setTimeout(function () {
        status.textContent = ''
      }, SAVED_FOR_MS)
    } catch (error) {
      toggle.checked = !wanted
      status.textContent = status.dataset.failed || ''
    } finally {
      toggle.disabled = false
    }
  })
})()
