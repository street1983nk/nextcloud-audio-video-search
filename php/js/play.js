/**
 * The playback page in plain browser JavaScript: no module, no bundler.
 *
 * The page is complete without this file. The source of the medium already
 * carries the time mark as a media fragment, so the browser seeks on its own.
 * This file adds three things and nothing else:
 *   1. a second seek once the metadata is known, for browsers that drop the
 *      fragment; a #t= in the page address wins over the ?t= of the server,
 *   2. the jump button, which sets the position and focuses the medium but
 *      never starts playback,
 *   3. the mapping of a playback error to one of the banners the template
 *      rendered hidden, with one HEAD request to the same origin,
 *   4. the button that saves the subtitle draft next to the file (04-UI-SPEC,
 *      E1 to E7): one POST with the request token, then exactly one of the
 *      seven result banners the template rendered hidden.
 *
 * It only flips hidden, disabled and aria-busy, moves the focus and sets a
 * file name through textContent. It never builds markup and never writes
 * markup from a string.
 */
'use strict'

;(function () {
  const button = document.getElementById('avs-sidecar')
  const results = document.getElementById('avs-sidecar-result')
  if (button === null || results === null) {
    return
  }

  // The only value of an answer that reaches the page, and only in this shape.
  const NAME = /^[^\/\\]{1,255}$/

  // One banner per answer of POST /sidecar/{fileId}; anything else is E7.
  function verdict (status, body) {
    const name = body !== null && typeof body.name === 'string' && NAME.test(body.name) ? body.name : null
    const reason = body !== null && typeof body.reason === 'string' ? body.reason : null
    if (status === 201 && name !== null) {
      return { id: 'avs-sidecar-e1', name }
    }
    if (status === 409 && name !== null) {
      return { id: 'avs-sidecar-e2', name }
    }
    if (status === 403 && reason === 'not_writable') {
      return { id: 'avs-sidecar-e3', name: null }
    }
    if (status === 403 && reason === 'blocked') {
      return { id: 'avs-sidecar-e4', name: null }
    }
    if (status === 400 && reason === 'name_too_long') {
      return { id: 'avs-sidecar-e5', name: null }
    }
    if (status === 429) {
      return { id: 'avs-sidecar-e6', name: null }
    }
    return { id: 'avs-sidecar-e7', name: null }
  }

  // The success is a status: the focus stays on the button. Every other
  // banner is an alert and takes the focus, like show() below.
  function present (result) {
    const banner = document.getElementById(result.id) ||
      document.getElementById('avs-sidecar-e7')
    if (banner === null) {
      return
    }
    if (result.name !== null) {
      const slot = banner.querySelector('.avs-export__name')
      if (slot !== null) {
        slot.textContent = result.name
      }
    }
    banner.hidden = false
    if (banner.id === 'avs-sidecar-e1') {
      button.focus()
    } else {
      banner.focus()
    }
  }

  button.hidden = false
  button.addEventListener('click', function () {
    if (button.disabled) {
      return
    }
    for (const banner of results.querySelectorAll('.avs-banner')) {
      banner.hidden = true
    }
    button.disabled = true
    button.setAttribute('aria-busy', 'true')

    fetch(button.dataset.url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        requesttoken: document.head.dataset.requesttoken,
        Accept: 'application/json',
      },
    })
      .then(function (response) {
        return response.json().then(function (body) {
          return verdict(response.status, body !== null && typeof body === 'object' ? body : null)
        }, function () {
          return verdict(response.status, null)
        })
      }, function () {
        return verdict(0, null)
      })
      .then(function (result) {
        button.disabled = false
        button.removeAttribute('aria-busy')
        present(result)
      })
  })
})()

;(function () {
  const media = document.getElementById('avs-media')
  if (media === null) {
    return
  }

  const HASH_START = /^#t=(\d{1,6}(?:\.\d{1,3})?)$/

  function seconds (raw) {
    const value = Number(raw)
    return Number.isFinite(value) && value > 0 ? value : 0
  }

  // The start the server validated, in the shape of the jump button label.
  const serverStart = seconds(media.dataset.start || '0')
  const fromHash = HASH_START.exec(window.location.hash)
  const start = fromHash !== null ? seconds(fromHash[1]) : serverStart

  function seekTo (time) {
    if (time <= 0) {
      return
    }
    try {
      media.currentTime = time
    } catch (ignored) {
      // A medium without metadata refuses the position; the fragment stays.
    }
  }

  if (media.readyState >= 1) {
    seekTo(start)
  } else {
    media.addEventListener('loadedmetadata', function () { seekTo(start) }, { once: true })
  }

  // The button names the time mark of the search hit, so it jumps there.
  const jump = document.getElementById('avs-jump')
  if (jump !== null && serverStart > 0) {
    jump.hidden = false
    jump.addEventListener('click', function () {
      seekTo(serverStart)
      media.focus()
    })
  }

  const reloads = document.querySelectorAll('.avs-reload')
  for (const button of reloads) {
    button.addEventListener('click', function () {
      window.location.reload()
    })
  }

  function show (name) {
    const banner = document.getElementById('avs-banner-' + name) ||
      document.getElementById('avs-banner-other')
    media.hidden = true
    if (jump !== null) {
      jump.hidden = true
    }
    if (banner !== null) {
      banner.hidden = false
      banner.focus()
    }
  }

  function byCode (code) {
    if (code === 2) {
      return 'network'
    }
    if (code === 3 || code === 4) {
      return 'format'
    }
    return 'other'
  }

  let handled = false
  function onError () {
    if (handled) {
      return
    }
    handled = true

    const code = media.error !== null ? media.error.code : 0
    const fallback = byCode(code)
    // A 403 or a 404 of WebDAV also arrives as an unsupported source, so the
    // status is asked once, without the fragment, on the same origin.
    const address = (media.getAttribute('src') || '').split('#')[0]
    if (address === '') {
      show(fallback)
      return
    }

    fetch(address, { method: 'HEAD', credentials: 'same-origin' })
      .then(function (response) {
        if (response.status === 403) {
          return 'download_blocked'
        }
        if (response.status === 404) {
          return 'moved'
        }
        return fallback
      }, function () {
        return 'network'
      })
      .then(show)
  }

  media.addEventListener('error', onError)
  if (media.error !== null) {
    onError()
  }
})()
